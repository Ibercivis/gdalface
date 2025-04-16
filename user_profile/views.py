"""
This module contains the views for the user_profile app
"""
from django.shortcuts import render, redirect
from django.contrib.auth import get_user_model
from django.contrib import messages
from django.db.models import Sum, Count, Avg
from georeferencing.models import GeoAttemptsByUserByDay
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

        geo = profile.geoattempts_done
        cp = profile.controlPointsDone
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
        
        # Calcular rankings
        # Ranking por número de tareas completadas
        users_by_tasks = UserProfile.objects.order_by('-geoattempts_done')
        
        # Obtener los primeros 10 perfiles de usuario por tareas completadas para el ranking
        task_ranking_profiles = list(users_by_tasks[:10])
        task_ranking = [(profile.user.username, profile.geoattempts_done, profile) for profile in task_ranking_profiles]
        
        # Encontrar la posición del usuario actual en el ranking de tareas
        user_task_position = 1
        for index, user_profile in enumerate(users_by_tasks):
            if user_profile.user_id == user.id:
                user_task_position = index + 1
                break
        
        # Ranking por tiempo dedicado
        users_by_time = UserProfile.objects.order_by('-time_spent')
        
        # Obtener los primeros 10 perfiles de usuario por tiempo para el ranking
        time_ranking_profiles = list(users_by_time[:10])
        time_ranking = [(profile.user.username, convert_time_spent(profile.time_spent), profile) for profile in time_ranking_profiles]
        
        # Encontrar la posición del usuario actual en el ranking de tiempo
        user_time_position = 1
        for index, user_profile in enumerate(users_by_time):
            if user_profile.user_id == user.id:
                user_time_position = index + 1
                break
        
        # Estadísticas globales
        total_users = UserProfile.objects.count()
        total_tasks_completed = UserProfile.objects.aggregate(total=Sum('geoattempts_done'))['total'] or 0
        total_time_spent = UserProfile.objects.aggregate(total=Sum('time_spent'))['total'] or 0
        total_time_formatted = convert_time_spent(total_time_spent)
        
        # Estadísticas promedio por usuario
        avg_tasks_per_user = UserProfile.objects.aggregate(avg=Avg('geoattempts_done'))['avg'] or 0
        avg_time_per_user = UserProfile.objects.aggregate(avg=Avg('time_spent'))['avg'] or 0
        avg_time_formatted = convert_time_spent(int(avg_time_per_user))
        
        # Porcentaje de contribución del usuario
        user_tasks_percentage = (geo / total_tasks_completed * 100) if total_tasks_completed > 0 else 0
        user_time_percentage = (profile.time_spent / total_time_spent * 100) if total_time_spent > 0 else 0
        
        context = {
            'user': user,
            'profile': profile,
            'time': time,
            'geo': geo,
            'cp': cp,
            'che': che,
            'geoattems_by_user_by_day': data,
            'task_ranking': task_ranking,
            'user_task_position': user_task_position,
            'time_ranking': time_ranking,
            'user_time_position': user_time_position,
            'total_users': total_users,
            'total_tasks_completed': total_tasks_completed,
            'total_time_spent': total_time_formatted,
            'avg_tasks_per_user': round(avg_tasks_per_user, 1),
            'avg_time_per_user': avg_time_formatted,
            'user_tasks_percentage': round(user_tasks_percentage, 2),
            'user_time_percentage': round(user_time_percentage, 2),
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
