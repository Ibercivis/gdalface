"""
This module contains the views for the user_profile app
"""
from django.shortcuts import render, redirect
from django.contrib.auth import get_user_model
from django.contrib import messages
from django.db.models import Sum, Count, Avg
from georeferencing.models import GeoAttempt, GeoAttemptsByUserByDay
from user_profile.models import UserProfile
from user_profile.forms import UserProfileForm
from django.contrib.auth.decorators import login_required
from django.contrib.auth import logout

User = get_user_model()

# Create your views here.
def user_view(request):
    """
    Handles the user profile view.

    This view checks if the user is authenticated and retrieves 
    various user profile attributes such as time spent, geo attempts done, 
    control points done...
    These attributes are then passed to the 'user.html' 
    template for rendering.

    Args:
        request (HttpRequest): The HTTP request object.

    Returns:
        HttpResponse: The rendered 'user.html' template with user 
        profile context if the user is authenticated.
        Otherwise, it returns the 'user.html' template without 
        additional context.
    """
    user = request.user
    if user.is_authenticated:
        # Obtener o crear el perfil de usuario si no existe
        try:
            profile = user.userprofile
        except UserProfile.DoesNotExist:
            # Si el perfil no existe, lo creamos
            profile = UserProfile.objects.create(user=user)
        
        time = convert_time_spent(profile.time_spent)

        # Contar las tareas completadas por el usuario directamente desde GeoAttempt
        user_completed_tasks = GeoAttempt.objects.filter(assignedUser=user, status='DONE').count()
        geo = user_completed_tasks  # Usar este valor en lugar de profile.geoattempts_done
        
        # Contar los puntos de control del usuario directamente desde GeoAttempt
        user_control_points = 0
        try:
            # Obtener los intentos completados por el usuario que tienen puntos de control
            user_completed_attempts = GeoAttempt.objects.filter(
                assignedUser=user,
                status='DONE',
                controlPoints__isnull=False
            )
            # Sumar la cantidad de puntos de control en cada intento
            for attempt in user_completed_attempts:
                if attempt.controlPoints and isinstance(attempt.controlPoints, list):
                    user_control_points += len(attempt.controlPoints)
        except Exception as e:
            print(f"Error calculating user control points: {str(e)}")
        
        cp = user_control_points  # Usar este valor en lugar de profile.controlPointsDone
        che = profile.cheating
        
        # Get the number of geo attempts done by the by day
        geoattems_by_user_by_day = []
        geoattems_by_user_by_day = GeoAttemptsByUserByDay.objects.filter(user=user)
        data = [
        {
            "date": item.date.isoformat(),  # Converts date to "YYYY-MM-DD"
            "numberGeoAttempts": item.numberGeoAttempts
        }
        for item in geoattems_by_user_by_day
        ]
        
        # Obtener todos los usuarios ordenados por posición para crear un ranking unificado
        users_by_tasks = list(UserProfile.objects.order_by('-geoattempts_done'))
        users_by_points = list(UserProfile.objects.order_by('-controlPointsDone'))
        users_by_time = list(UserProfile.objects.order_by('-time_spent'))
        
        # Crear una estructura unificada para el ranking
        top_users = {}
        
        # Limitar a los 20 mejores usuarios
        limit = 20
        
        # Añadir posiciones en el ranking de tareas
        for index, user_profile in enumerate(users_by_tasks[:limit]):
            username = user_profile.user.username
            if username not in top_users:
                top_users[username] = {
                    'username': username,
                    'profile': user_profile,
                    'tasks_position': index + 1,
                    'tasks': user_profile.geoattempts_done,
                    'points_position': None, 
                    'points': user_profile.controlPointsDone,
                    'time_position': None,
                    'time_spent': convert_time_spent(user_profile.time_spent),
                    'time_seconds': user_profile.time_spent
                }
        
        # Añadir posiciones en el ranking de puntos
        for index, user_profile in enumerate(users_by_points[:limit]):
            username = user_profile.user.username
            if username in top_users:
                top_users[username]['points_position'] = index + 1
            else:
                # Buscar posición en ranking de tareas (puede estar fuera del top)
                task_pos = next((i + 1 for i, up in enumerate(users_by_tasks) if up.user.username == username), None)
                
                top_users[username] = {
                    'username': username,
                    'profile': user_profile,
                    'tasks_position': task_pos,
                    'tasks': user_profile.geoattempts_done,
                    'points_position': index + 1, 
                    'points': user_profile.controlPointsDone,
                    'time_position': None,
                    'time_spent': convert_time_spent(user_profile.time_spent),
                    'time_seconds': user_profile.time_spent
                }
        
        # Añadir posiciones en el ranking de tiempo
        for index, user_profile in enumerate(users_by_time[:limit]):
            username = user_profile.user.username
            if username in top_users:
                top_users[username]['time_position'] = index + 1
            else:
                # Buscar posición en ranking de tareas (puede estar fuera del top)
                task_pos = next((i + 1 for i, up in enumerate(users_by_tasks) if up.user.username == username), None)
                # Buscar posición en ranking de puntos (puede estar fuera del top)
                points_pos = next((i + 1 for i, up in enumerate(users_by_points) if up.user.username == username), None)
                
                top_users[username] = {
                    'username': username,
                    'profile': user_profile,
                    'tasks_position': task_pos,
                    'tasks': user_profile.geoattempts_done,
                    'points_position': points_pos, 
                    'points': user_profile.controlPointsDone,
                    'time_position': index + 1,
                    'time_spent': convert_time_spent(user_profile.time_spent),
                    'time_seconds': user_profile.time_spent
                }
        
        # Asegurarse de que el usuario actual esté en el ranking
        if user.username not in top_users:
            # Buscar posiciones del usuario actual
            user_task_position = next((i + 1 for i, up in enumerate(users_by_tasks) if up.user.username == user.username), None)
            user_points_position = next((i + 1 for i, up in enumerate(users_by_points) if up.user.username == user.username), None)
            user_time_position = next((i + 1 for i, up in enumerate(users_by_time) if up.user.username == user.username), None)
            
            top_users[user.username] = {
                'username': user.username,
                'profile': profile,
                'tasks_position': user_task_position,
                'tasks': profile.geoattempts_done,
                'points_position': user_points_position, 
                'points': profile.controlPointsDone,
                'time_position': user_time_position,
                'time_spent': time,
                'time_seconds': profile.time_spent
            }
        
        # Convertir el diccionario en una lista para ordenarlo
        unified_ranking = list(top_users.values())
        
        # Ordenar por tareas completadas (prioridad principal)
        unified_ranking.sort(key=lambda x: (-(x['tasks'] if x['tasks'] is not None else 0)))
        
        # Encontrar posiciones del usuario actual
        user_task_position = next((i + 1 for i, up in enumerate(users_by_tasks) if up.user.username == user.username), None)
        user_points_position = next((i + 1 for i, up in enumerate(users_by_points) if up.user.username == user.username), None)
        user_time_position = next((i + 1 for i, up in enumerate(users_by_time) if up.user.username == user.username), None)
        
        # Estadísticas globales
        total_users = User.objects.count()
        
        # Contar el total de tareas en el sistema
        total_tasks = GeoAttempt.objects.count()
        
        # Contar tareas completadas (solo aquellas con status='DONE')
        total_tasks_completed = GeoAttempt.objects.filter(status='DONE').count()
        
        total_time_spent = UserProfile.objects.aggregate(total=Sum('time_spent'))['total'] or 0
        total_time_formatted = convert_time_spent(total_time_spent)
        
        # Calcular el total de puntos de control en el sistema
        total_control_points = 0
        try:
            # Obtenemos los geoattempts completados que tienen puntos de control
            completed_attempts = GeoAttempt.objects.filter(
                status='DONE',
                controlPoints__isnull=False
            )
            
            # Sumamos la cantidad de puntos de control en cada intento
            for attempt in completed_attempts:
                # controlPoints es un JSONField que puede contener una lista de puntos
                if attempt.controlPoints and isinstance(attempt.controlPoints, list):
                    total_control_points += len(attempt.controlPoints)
        except Exception as e:
            # Log the error but continue with total_control_points = 0
            print(f"Error calculating total control points: {str(e)}")
        
        # Estadísticas promedio por usuario
        avg_tasks_per_user = 0
        if total_users > 0:
            avg_tasks_per_user = round(total_tasks_completed / total_users, 1)
            
        avg_time_per_user = UserProfile.objects.aggregate(avg=Avg('time_spent'))['avg'] or 0
        avg_time_formatted = convert_time_spent(int(avg_time_per_user))
        
        # Porcentaje de contribución del usuario (porcentaje del total que ha contribuido el usuario)
        user_tasks_percentage = (geo / total_tasks_completed * 100) if total_tasks_completed > 0 else 0
        user_time_percentage = (profile.time_spent / total_time_spent * 100) if total_time_spent > 0 else 0
        user_control_points_percentage = (cp / total_control_points * 100) if total_control_points > 0 else 0
        
        # Asegurarnos de que los porcentajes no excedan el 100%
        user_tasks_percentage = min(user_tasks_percentage, 100)
        user_time_percentage = min(user_time_percentage, 100)
        user_control_points_percentage = min(user_control_points_percentage, 100)
        
        context = {
            'user': user,
            'profile': profile,
            'time': time,
            'geo': geo,
            'cp': cp,
            'che': che,
            'geoattems_by_user_by_day': data,
            'unified_ranking': unified_ranking,
            'user_task_position': user_task_position,
            'user_time_position': user_time_position,
            'user_points_position': user_points_position,
            'total_users': total_users,
            'total_tasks': total_tasks,
            'total_tasks_completed': total_tasks_completed,
            'total_time_spent': total_time_formatted,
            'avg_tasks_per_user': avg_tasks_per_user,
            'avg_time_per_user': avg_time_formatted,
            'user_tasks_percentage': round(user_tasks_percentage, 2),
            'user_time_percentage': round(user_time_percentage, 2),
            'user_control_points_percentage': round(user_control_points_percentage, 2),
        }
        return render(request, 'user.html', context)
    return redirect('/accounts/')


def edit_profile(request):
    """
    View for editing user profile.
    
    Handles both GET and POST requests. For GET requests, it shows the profile
    editing form. For POST requests, it validates the form data and updates
    the profile if valid.
    
    Args:
        request: The HTTP request object
        
    Returns:
        HttpResponse: The rendered 'edit_profile.html' template or a redirect to the profile page
    """
    if not request.user.is_authenticated:
        return redirect('/accounts/login/')
    
    try:
        profile = request.user.userprofile
    except UserProfile.DoesNotExist:
        profile = UserProfile.objects.create(user=request.user)
    
    if request.method == 'POST':
        form = UserProfileForm(request.POST, request.FILES, instance=profile)
        if form.is_valid():
            form.save()
            messages.success(request, 'Your profile has been updated successfully!')
            return redirect('/user-profile/')
    else:
        form = UserProfileForm(instance=profile)
    
    return render(request, 'edit_profile.html', {
        'form': form,
        'user': request.user
    })


def convert_time_spent(total_seconds):
    """
    Convierte el tiempo total en segundos a un formato legible con días, horas y minutos.
    Solo muestra las unidades de tiempo que son necesarias (por ejemplo, no muestra "0 días").
    
    Args:
        total_seconds: Tiempo total en segundos
        
    Returns:
        str: Tiempo formateado en una cadena legible
    """
    # Calculate days, hours, minutes
    days, remainder = divmod(total_seconds, 86400)  # 86400 seconds = 1 day
    hours, remainder = divmod(remainder, 3600)      # 3600 seconds = 1 hour
    minutes = remainder // 60                        # 60 seconds = 1 minute
    
    # Crear partes del tiempo con formato
    time_parts = []
    
    # Solo agregar unidades si son mayores que 0
    if days > 0:
        time_parts.append(f"{days} {'día' if days == 1 else 'días'}")
    if hours > 0:
        time_parts.append(f"{hours} {'hora' if hours == 1 else 'horas'}")
    if minutes > 0 or (days == 0 and hours == 0):  # Siempre mostramos minutos si no hay días ni horas
        time_parts.append(f"{minutes} {'minuto' if minutes == 1 else 'minutos'}")
    
    # Unir las partes con comas y "y" para la última parte
    if len(time_parts) > 1:
        return ", ".join(time_parts[:-1]) + " y " + time_parts[-1]
    elif len(time_parts) == 1:
        return time_parts[0]
    else:
        return "0 minutos"  # Caso extremo, nunca debería ocurrir si total_seconds >= 0


@login_required
def delete_account(request):
    """
    Vista para eliminar la cuenta de usuario.
    
    Antes de eliminar la cuenta, establece como NULL el campo assignedUser en todos los
    registros GeoAttempt asociados con el usuario, para mantener los registros de
    georreferenciación intactos pero sin asociación a un usuario específico.
    
    Args:
        request: El objeto de solicitud HTTP
        
    Returns:
        HttpResponse: Redirección a la página principal
    """
    if request.method == "POST":
        user = request.user
        
        # Importar el modelo GeoAttempt
        from georeferencing.models import GeoAttempt
        
        # Establecer como NULL el campo assignedUser en todos los registros asociados
        # en lugar de eliminarlos o transferirlos a otro usuario
        GeoAttempt.objects.filter(assignedUser=user).update(assignedUser=None)
        
        # Desconectar al usuario
        logout(request)
        
        # Eliminar el usuario y toda su información relacionada
        user.delete()
        messages.success(request, "Tu cuenta ha sido eliminada permanentemente.")
        return redirect('index')
    
    return render(request, 'delete_account.html')
