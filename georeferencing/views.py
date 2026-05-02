from django.shortcuts import get_object_or_404
from django.utils import timezone

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from drf_yasg.utils import swagger_auto_schema
from rest_framework.parsers import JSONParser
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated  # Add this import
from rest_framework.permissions import AllowAny
from .serializers import GeoAttemptSerializer, ImageSerializer, MiniGeoAttemptSerializer
from .models import (
    GeoAttempt, Image, Batch, GeoAttemptsByUserByDay, TutorialEvent,
    Challenge, ChallengeParticipant,
)
from user_profile.models import UserProfile
import os
import shutil
import subprocess
import random
from haversine import haversine
from datetime import datetime, timedelta
# import isAuthenticated from rest_framework.permissions
# from django.contrib.auth.decorators import login_required




class GeoAttemptView(APIView):
    """
    GeoAttemptView
    This class-based view handles the API endpoints for image geo attempts.
    Attributes:
        parser_classes (tuple): A tuple of parser classes used for request parsing
    Methods:
        get(request): Retrieves all image geo attempts.
        post(request): Creates a new image geo attempt.
    """
    parser_classes = (JSONParser,)

    @swagger_auto_schema(
        tags=['02. GeoAttempts'],
        operation_summary="Get all image geo attempts")
    def get(self, request):
        geoattemps = GeoAttempt.objects.all()
        serializer = MiniGeoAttemptSerializer(geoattemps, many=True)
        return Response(serializer.data)

    @swagger_auto_schema(
        request_body=GeoAttemptSerializer,
        tags=['02. GeoAttempts'],
        operation_summary="Post an image geo attempt")
    def post(self, request):
        serializer = GeoAttemptSerializer(
            data=request.data, context={'request': request})
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class PendingGeoAttemptView(APIView):
    """
    API view to handle pending GeoAttempts.
    - GET /geoattempt-pending/: Get a random 'PENDING' GeoAttempt from any batch.
    - GET /geoattempt-pending/<pk>/: Get a random 'PENDING' GeoAttempt from a specific batch.
    """

    @swagger_auto_schema(
        tags=['02. GeoAttempts'],
        operation_summary="Get a random 'PENDING' geo attempt (optionally from a specific batch)")
    def get(self, request, pk=None):
        # Determine the queryset based on whether pk (batch ID) is provided
        if pk is None:
            # No batch specified: get all pending GeoAttempts
            pending_geoattempts = GeoAttempt.objects.filter(status="PENDING")
        else:
            # Batch specified: get pending GeoAttempts for that batch
            print("Batch ID provided:", pk)
            try:
                batch = Batch.objects.get(id=pk)
                print(batch)
                pending_geoattempts = GeoAttempt.objects.filter(status="PENDING", image__batch=batch)
            except Batch.DoesNotExist:
                return Response({"error": "Batch not found."}, status=status.HTTP_404_NOT_FOUND)

        # Check if any pending GeoAttempts exist
        if not pending_geoattempts.exists():
            error_msg = "No pending geo attempts found" + (" in this batch." if pk else ".")
            return Response({"error": error_msg}, status=status.HTTP_404_NOT_FOUND)

        # Select a random GeoAttempt and update it
        geoattempt = random.choice(pending_geoattempts)
        geoattempt.status = 'ASSIGNED'
        geoattempt.assignedDateTime = timezone.now()
        geoattempt.finishedDateTime = None
        geoattempt.numberTries = 0
        geoattempt.controlPoints = []  # Assuming controlPoints is a list in your JSONField
        if request.user.is_authenticated:
            geoattempt.assignedUser = request.user
        else:
            # Handle case where user isn’t authenticated (optional)
            geoattempt.assignedUser = None  # Or raise an error if assignment requires a user
        geoattempt.save()

        # Serialize and return the GeoAttempt
        serializer = GeoAttemptSerializer(geoattempt)
        data = dict(serializer.data)

        # Append personal stats for authenticated users
        if request.user.is_authenticated:
            from django.db.models import Count
            user = request.user
            all_done = GeoAttempt.objects.filter(status='DONE')
            user_done = all_done.filter(assignedUser=user)

            # --- Tasks ---
            tasks_done = user_done.count()
            tasks_board = list(all_done.values('assignedUser').annotate(total=Count('id')).order_by('-total'))
            tasks_rank = next((i + 1 for i, u in enumerate(tasks_board) if u['assignedUser'] == user.id), None)
            tasks_to_next = (tasks_board[tasks_rank - 2]['total'] - tasks_done + 1) if tasks_rank and tasks_rank > 1 else 0
            tasks_to_first = (tasks_board[0]['total'] - tasks_done) if tasks_rank and tasks_rank > 1 else 0

            # --- Control points (per user, computed in Python) ---
            all_cp_by_user = {}
            for a in all_done.only('assignedUser_id', 'controlPoints'):
                uid = a.assignedUser_id
                if uid is None:
                    continue
                n = len(a.controlPoints) if a.controlPoints and isinstance(a.controlPoints, list) else 0
                all_cp_by_user[uid] = all_cp_by_user.get(uid, 0) + n
            my_cp = all_cp_by_user.get(user.id, 0)
            cp_board = sorted(all_cp_by_user.items(), key=lambda x: -x[1])
            cp_rank = next((i + 1 for i, (uid, _) in enumerate(cp_board) if uid == user.id), None)
            cp_to_next = (cp_board[cp_rank - 2][1] - my_cp + 1) if cp_rank and cp_rank > 1 else 0
            cp_to_first = (cp_board[0][1] - my_cp) if cp_rank and cp_rank > 1 else 0

            # --- Time (hours) ---
            all_time_by_user = {}
            for a in all_done.filter(finishedDateTime__isnull=False, assignedDateTime__isnull=False).only(
                    'assignedUser_id', 'finishedDateTime', 'assignedDateTime'):
                uid = a.assignedUser_id
                if uid is None:
                    continue
                secs = (a.finishedDateTime - a.assignedDateTime).total_seconds()
                if secs > 0:
                    all_time_by_user[uid] = all_time_by_user.get(uid, 0) + secs
            my_secs = all_time_by_user.get(user.id, 0)
            my_hours = round(my_secs / 3600, 1)
            time_board = sorted(all_time_by_user.items(), key=lambda x: -x[1])
            time_rank = next((i + 1 for i, (uid, _) in enumerate(time_board) if uid == user.id), None)
            time_to_next_h = round((time_board[time_rank - 2][1] - my_secs + 60) / 3600, 1) if time_rank and time_rank > 1 else 0
            time_to_first_h = round((time_board[0][1] - my_secs) / 3600, 1) if time_rank and time_rank > 1 else 0

            data['user_stats'] = {
                'tasks_done': tasks_done,
                'tasks_rank': tasks_rank,
                'tasks_to_next': tasks_to_next,
                'tasks_to_first': tasks_to_first,
                'control_points': my_cp,
                'cp_rank': cp_rank,
                'cp_to_next': cp_to_next,
                'cp_to_first': cp_to_first,
                'hours': my_hours,
                'time_rank': time_rank,
                'time_to_next': time_to_next_h,
                'time_to_first': time_to_first_h,
            }

        return Response(data)


class GeoAttemptIndividualView(APIView):
    """
    API view for patching and deleting an image geo attempt.
    Methods:
    - patch: Patch an image geo attempt.
    - delete: Delete an image geo attempt.
    """
    parser_classes = (JSONParser,)
    # TODO: Remove print statements
    def max_distance(self, points):
        print("Input to max_distance:", points)
        if not points or not isinstance(points, (list, tuple)) or len(points) < 2:
            raise ValueError("At least two points are required in a list or tuple")
    
        max_dist = 0
        for i, point1 in enumerate(points):
            for point2 in points[i + 1:]:
                print(f"Point1: {point1}, Point2: {point2}")
                if not all(k in point1 for k in ['lat', 'lon']) or not all(k in point2 for k in ['lat', 'lon']):
                    raise ValueError("Each point must have 'lat' and 'lon' keys")
            
                lat1, lon1 = float(point1['lat']), float(point1['lon'])
                lat2, lon2 = float(point2['lat']), float(point2['lon'])
                coord1 = (lat1, lon1)
                coord2 = (lat2, lon2)
                print(f"Coords to haversine: {coord1}, {coord2}")
                dist = haversine(coord1, coord2)
                print(f"Distance: {dist}")
                if dist > max_dist:
                    max_dist = dist
        return max_dist
    
    # TODO: Review if this is ok or we need to change the zooms
    def get_zooms(self, max_dist):
        if max_dist < 0.5:
            return "15-18"
        elif max_dist < 1:
            return "14-17"
        elif max_dist < 2:
            return "13-16"
        elif max_dist < 4:
            return "12-15"
        elif max_dist < 8:
            return "11-14"
        elif max_dist < 16:
            return "10-13"
        elif max_dist < 32:
            return "9-12"
        elif max_dist < 64:
            return "8-11"
        elif max_dist < 128:
            return "7-10"
        elif max_dist < 256:
            return "6-9"
        elif max_dist < 512:
            return "5-8"
        else:
            return "4-7"

    @swagger_auto_schema(
        tags=['02. GeoAttempts'],
        operation_summary="Get an image geo attempt")
    def get(self, request, pk=None):
        geoattemp = get_object_or_404(GeoAttempt, pk=pk)
        # Changing the geoattemp status to ASSIGNED

        serializer = GeoAttemptSerializer(geoattemp)
        return Response(serializer.data)

    @swagger_auto_schema(
        request_body=GeoAttemptSerializer,
        tags=['02. GeoAttempts'],
        operation_summary="Patch an image geo attempt")
    def patch(self, request, pk=None):
        geoattemp = get_object_or_404(GeoAttempt, pk=pk)
        print(request.data)
        serializer = GeoAttemptSerializer(
            geoattemp, data=request.data, partial=True)
        if serializer.is_valid():

            # We are receiving this status from user, so that means
            # that it's not finished yet, and the user is asking for
            # a new try
            if request.data['status'] == 'ASSIGNED':
                print('Starting the testing process')
                # We increment the number of tries
                geoattemp.numberTries += 1
                geoattemp.maxZoom = 5
                geoattemp.save()

                # Ensure the georeferenced directory exists
                if not os.path.exists('media/georeferenced'):
                    os.makedirs('media/georeferenced')

                # First command: gdal_translate
                command = 'gdal_translate -of GTiff'
                for item in request.data['control_points']:
                    command += ' -gcp ' + \
                        str(item['actualPx']) + ' ' + str(item['actualPy'])
                    command += ' ' + str(item['lon']) + ' ' + str(item['lat'])
                command += ' media/original/' + geoattemp.image.name
                command += ' media/georeferenced/' + \
                    geoattemp.image.name + geoattemp.hash + '.tif'
                print(command)
                try:
                    subprocess.run(command, shell=True, check=True,
                                   capture_output=True, text=True)
                except subprocess.CalledProcessError as e:
                    return Response({"error": f"gdal_translate failed: {e.stderr}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

                # Second command: gdalwarp
                # Check the # of points before enable tps (-order n to pylynomial)
                tif_path = 'media/georeferenced/' + geoattemp.image.name + geoattemp.hash + '.tif'
                tif_tmp_path = 'media/georeferenced/' + geoattemp.image.name + geoattemp.hash + '_warped.tif'
                command = 'gdalwarp -r bilinear -tps -t_srs EPSG:4326'
                command += ' ' + tif_path
                command += ' ' + tif_tmp_path
                print(command)

                try:
                    subprocess.run(command, shell=True, check=True,
                                   capture_output=True, text=True)
                    os.replace(tif_tmp_path, tif_path)
                except subprocess.CalledProcessError as e:
                    if os.path.exists(tif_tmp_path):
                        os.remove(tif_tmp_path)
                    return Response({"error": f"gdalwarp failed: {e.stderr}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

                # Third command: Remove previous tiles
                command = 'rm -r media/georeferenced/' + geoattemp.image.name + geoattemp.hash
                print(command)
                if os.path.exists('media/georeferenced/' + geoattemp.image.name + geoattemp.hash):
                    try:
                        subprocess.run(command, shell=True, check=True,
                                       capture_output=True, text=True)
                    except subprocess.CalledProcessError as e:
                        return Response({"error": f"Failed to remove previous tiles: {e.stderr}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

                # Fourth command: (-r bilinear is slower, but....)
                # zoom will depend on the focal length
                # Show max distance between two points
                mx = self.max_distance(request.data['control_points'])
                print(mx)
                zoom = self.get_zooms(mx)
                print(zoom)
                command = 'gdal2tiles.py -z ' + zoom + ' -r near -s EPSG:4326'
                command += ' media/georeferenced/' + \
                    geoattemp.image.name + geoattemp.hash + '.tif'
                command += ' media/georeferenced/' + geoattemp.image.name + geoattemp.hash
                print(command)

                try:
                    subprocess.run(command, shell=True,
                                   capture_output=True, text=True, check=True)
                except subprocess.CalledProcessError as e:
                    return Response({"error": f"gdal2tiles.py failed: {e.stderr}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
                return Response(serializer.data, status=status.HTTP_200_OK)
            # That means that the user is happy with the final result
            elif request.data['status'] == 'DONE':
                # Clean up temporary tiles generated during Try
                tile_dir = 'media/georeferenced/' + geoattemp.image.name + geoattemp.hash
                tile_tif = tile_dir + '.tif'
                if os.path.exists(tile_tif):
                    os.remove(tile_tif)
                if os.path.exists(tile_dir):
                    shutil.rmtree(tile_dir)
                # let's start the georeferencing process
                # for the moment, launch a batch script
                print('Submitting the final result')
                print(request.data['controlPoints'])
                geoattemp.finishedDateTime = timezone.now()
                geoattemp.save()
                spend_time = (geoattemp.finishedDateTime -
                              geoattemp.assignedDateTime).total_seconds()
                # Now, if the user is logged in, we can add a geoattempt to today
                if geoattemp.assignedUser:
                    print('User is authenticated')
                    user_profile, created = UserProfile.objects.get_or_create(
                        user=geoattemp.assignedUser)
                    if created:
                        print('User profile created')
                    user_profile.geoattempts_done += 1
                    user_profile.time_spent += spend_time
                    user_profile.controlPointsDone += len(
                        request.data['controlPoints'])
                    user_profile.save()

                    # Challenge progress: if the user has an active enrollment
                    # whose challenge applies (active status + matching batch
                    # or general), add the submitted CPs to its cached counter.
                    cp_added = len(request.data['controlPoints'])
                    if cp_added:
                        from django.db.models import F, Q
                        now = timezone.now()
                        image_batch_id = geoattemp.image.batch_id
                        enrollment = (
                            ChallengeParticipant.objects
                            .select_related('challenge')
                            .filter(
                                user=geoattemp.assignedUser,
                                left_at__isnull=True,
                                challenge__is_paused=False,
                                challenge__start_at__lte=now,
                                challenge__end_at__gt=now,
                            )
                            .filter(
                                Q(challenge__batch__isnull=True)
                                | Q(challenge__batch_id=image_batch_id)
                            )
                            .first()
                        )
                        if enrollment:
                            ChallengeParticipant.objects.filter(
                                pk=enrollment.pk,
                            ).update(cached_cp_count=F('cached_cp_count') + cp_added)

                    # Now, we can add a geoattempt to today
                    today = timezone.now().date()
                    geoattempts_today, created = GeoAttemptsByUserByDay.objects.get_or_create(
                        user=geoattemp.assignedUser, date=today)
                    if created:
                        print('GeoAttemptsByUserByDay created')
                        geoattempts_today.numberGeoAttempts += 1
                        geoattempts_today.save()
                    else:
                        print('GeoAttemptsByUserByDay updated')
                        geoattempts_today.numberGeoAttempts += 1
                        geoattempts_today.save()

                if spend_time < 10:
                    print('User is cheating')
                    geoattemp.finishedDateTime = None
                    geoattemp.save()
                    user_profile, created = UserProfile.objects.get_or_create(
                        user=geoattemp.assignedUser)
                    if created:
                        print('User profile created')
                    user_profile.cheating += 1
                    user_profile.save()
                    return Response({"error": f"Are you cheating?. {spend_time}"}, status=status.HTTP_400_BAD_REQUEST)

                serializer.save()

            # That means that the user click on "skip" button
            # So returning back to pending status
            elif request.data['status'] == 'PENDING':
                # Clean up temporary tiles generated during Try
                tile_dir = 'media/georeferenced/' + geoattemp.image.name + geoattemp.hash
                tile_tif = tile_dir + '.tif'
                if os.path.exists(tile_tif):
                    os.remove(tile_tif)
                if os.path.exists(tile_dir):
                    shutil.rmtree(tile_dir)
                # Come back to pending status
                print('Come back to pending status')
                # We are doing it mainly for control panel
                geoattemp.skipped += 1
                geoattemp.assignedDateTime = None
                geoattemp.finishedDateTime = None
                geoattemp.numberTries = 0
                geoattemp.assignedUser = None
                geoattemp.status = 'PENDING'
                geoattemp.save()
                serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @swagger_auto_schema(
        tags=['02. GeoAttempts'],
        operation_summary="Delete a geo attempt")
    def delete(self, request, pk=None):
        geoattemp = get_object_or_404(GeoAttempt, pk=pk)
        geoattemp.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ImageView(APIView):
    @swagger_auto_schema(
        tags=['03. Images'],
        operation_summary="Get all images")
    def get(self, request):
        """
        Handles GET requests to retrieve all Image objects.

        Args:
            request (Request): The HTTP request object.

        Returns:
            Response: A Response object containing serialized data of all Image objects.
        """
        images = Image.objects.all()
        serializer = ImageSerializer(images, many=True)
        return Response(serializer.data)

    @swagger_auto_schema(
        request_body=ImageSerializer,
        tags=['03. Images'],
        operation_summary="Post an image")
    def post(self, request):
        """
        Handle POST requests to create a new image entry.

        This method deserializes the incoming request data using the ImageSerializer.
        If the data is valid, it saves the new image entry and returns the serialized data
        with a 201 Created status. If the data is not valid, it will return an error response.

        Args:
            request (Request): The HTTP request object containing the data to be deserialized.

        Returns:
            Response: A Response object containing the serialized data and HTTP status code.
        """
        serializer = ImageSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)


class ImageIndividualView(APIView):
    """
    ImageIndividualView is a class-based view that handles HTTP GET, PATCH,
    and DELETE requests for individual Image instances.

    Methods:
        get(request, pk=None):



        patch(request, pk=None):

                data to update the Image instance.
                pk (int, optional): The primary key of the Image instance to update.


        delete(request, pk=None):
    """

    @swagger_auto_schema(
        tags=['03. Images'],
        operation_summary="Get an image")
    def get(self, request, pk=None):
        """
        Handle GET request to retrieve an image by its primary key (pk).

        Args:
            request (Request): The HTTP request object.
            pk (int, optional): The primary key of the image to retrieve.

        Returns:
            Response: A Response object containing the serialized image data.
        """
        image = get_object_or_404(Image, pk=pk)
        serializer = ImageSerializer(image)
        return Response(serializer.data)

    @swagger_auto_schema(
        request_body=ImageSerializer,
        tags=['03. Images'],
        operation_summary="Patch an image")
    def patch(self, request, pk=None):
        """
        Partially updates an Image instance.

        Args:
            request (Request): The HTTP request object containing the partial
            data to update the Image instance. pk (int, optional): 
            The primary key of the Image instance to update.

        Returns:
            Response: A Response object containing the serialized data of the 
            updated Image instance if the update is successful. If the update 
            fails, returns a Response object containing the validation errors 
            with a 400 Bad Request status.
        """
        image = get_object_or_404(Image, pk=pk)
        serializer = ImageSerializer(image, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @swagger_auto_schema(
        tags=['03. Images'],
        operation_summary="Delete an image")
    def delete(self, request, pk=None):
        """
        Delete an image instance.

        Args:
            request (Request): The HTTP request object.
            pk (int, optional): The primary key of the image to be deleted.

        Returns:
            Response: A response with HTTP status 204 (No Content) indicating successful deletion.
        """
        image = get_object_or_404(Image, pk=pk)
        image.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
    
class GeoAttemptsCalendarView(APIView):
    permission_classes = [IsAuthenticated]  # Restrict to logged-in users

    def get(self, request):
        # Get the current logged-in user
        user = request.user
        
        # Current date
        current_date = datetime.now()
        
        # Start date: one year back from today
        start_date = datetime(current_date.year - 1, current_date.month, current_date.day)
        
        # End date: end of the current month
        end_date = datetime(current_date.year, current_date.month + 1, 1) - timedelta(days=1)
        if current_date.month == 12:  # Handle December case
            end_date = datetime(current_date.year + 1, 1, 1) - timedelta(days=1)
            
        print(f"Calendar range: {start_date} to {end_date}")
        
        # Generate all days in the range
        all_days = [
            start_date + timedelta(days=i)
            for i in range((end_date - start_date).days + 1)
        ]
        
        # Fetch GeoAttempts data for the user in this date range
        geo_attempts = GeoAttemptsByUserByDay.objects.filter(
            user=user,
            date__gte=start_date,
            date__lte=end_date
        ).values('date', 'numberGeoAttempts')
        
        print(f"Found {len(geo_attempts)} geo attempts in date range")
        
        # Convert to dict for lookup
        attempts_dict = {str(item['date']): item['numberGeoAttempts'] for item in geo_attempts}
        
        # Build calendar data
        calendar_data = [
            {
                "date": day.strftime("%Y-%m-%d"),
                "count": attempts_dict.get(day.strftime("%Y-%m-%d"), 0)
            }
            for day in all_days
        ]
        
        return Response(calendar_data)


class TutorialEventView(APIView):
    permission_classes = [AllowAny]

    @swagger_auto_schema(
        tags=['03. Tutorial'],
        operation_summary="Log a tutorial event")
    def post(self, request):
        event = request.data.get('event')
        valid = {'started', 'step', 'completed', 'dismissed'}
        if event not in valid:
            return Response({'error': 'invalid event'}, status=status.HTTP_400_BAD_REQUEST)

        step = request.data.get('step')
        if step is not None:
            try:
                step = int(step)
            except (TypeError, ValueError):
                return Response({'error': 'invalid step'}, status=status.HTTP_400_BAD_REQUEST)

        user = request.user if request.user.is_authenticated else None
        if not request.session.session_key:
            request.session.save()
        session_key = request.session.session_key or ''

        TutorialEvent.objects.create(
            user=user,
            session_key=session_key,
            event=event,
            step=step,
        )
        return Response({'ok': True}, status=status.HTTP_201_CREATED)


def _serialize_challenge(ch, request_user=None):
    enrolled = False
    if request_user and request_user.is_authenticated:
        enrolled = ChallengeParticipant.objects.filter(
            challenge=ch, user=request_user, left_at__isnull=True,
        ).exists()
    return {
        'id': ch.id,
        'name': ch.name,
        'description': ch.description,
        'batch_id': ch.batch_id,
        'batch_name': ch.batch.name if ch.batch_id else None,
        'start_at': ch.start_at.isoformat(),
        'end_at': ch.end_at.isoformat(),
        'target_bronze': ch.target_bronze,
        'target_silver': ch.target_silver,
        'target_gold': ch.target_gold,
        'is_paused': ch.is_paused,
        'status': ch.status,
        'total_cp': ch.total_cp(),
        'participants_count': ch.participants.count(),
        'is_enrolled': enrolled,
    }


class ChallengeListView(APIView):
    permission_classes = [AllowAny]

    @swagger_auto_schema(
        tags=['04. Challenges'],
        operation_summary='List challenges (active, upcoming, finished)')
    def get(self, request):
        qs = Challenge.objects.all().select_related('batch')
        data = [_serialize_challenge(ch, request.user) for ch in qs]
        # Group by status for convenience.
        grouped = {'active': [], 'upcoming': [], 'paused': [], 'finished': []}
        for d in data:
            grouped.setdefault(d['status'], []).append(d)
        return Response({'challenges': data, 'grouped': grouped})


class ChallengeDetailView(APIView):
    permission_classes = [AllowAny]

    @swagger_auto_schema(
        tags=['04. Challenges'],
        operation_summary='Challenge progress and leaderboard')
    def get(self, request, pk):
        ch = get_object_or_404(Challenge, pk=pk)
        data = _serialize_challenge(ch, request.user)

        leaderboard_qs = (
            ch.participants
            .select_related('user')
            .order_by('-cached_cp_count', 'joined_at')
        )
        leaderboard = []
        my_rank = None
        my_cp = None
        for i, p in enumerate(leaderboard_qs[:50], start=1):
            row = {
                'rank': i,
                'username': p.user.username,
                'cp_count': p.cached_cp_count,
                'is_active': p.left_at is None,
            }
            leaderboard.append(row)
            if request.user.is_authenticated and p.user_id == request.user.id:
                my_rank = i
                my_cp = p.cached_cp_count

        if my_rank is None and request.user.is_authenticated:
            mine = ChallengeParticipant.objects.filter(
                challenge=ch, user=request.user,
            ).first()
            if mine:
                my_cp = mine.cached_cp_count
                # Compute rank via count of higher scores.
                better = ch.participants.filter(
                    cached_cp_count__gt=mine.cached_cp_count,
                ).count()
                my_rank = better + 1

        data['leaderboard'] = leaderboard
        data['my_rank'] = my_rank
        data['my_cp'] = my_cp
        return Response(data)


class ChallengeJoinView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        tags=['04. Challenges'],
        operation_summary='Join a challenge (auto-leaves any other active enrollment)')
    def post(self, request, pk):
        from django.db import transaction
        ch = get_object_or_404(Challenge, pk=pk)
        if ch.status == 'finished':
            return Response({'error': 'challenge is finished'}, status=400)

        with transaction.atomic():
            # Close any other active enrollment for this user.
            other = ChallengeParticipant.objects.select_for_update().filter(
                user=request.user, left_at__isnull=True,
            ).exclude(challenge=ch).first()
            if other:
                other.left_at = timezone.now()
                other.save(update_fields=['left_at'])

            # Create or revive enrollment for the target challenge.
            enrollment, created = ChallengeParticipant.objects.select_for_update().get_or_create(
                challenge=ch, user=request.user,
            )
            if not created and enrollment.left_at is not None:
                enrollment.left_at = None
                enrollment.save(update_fields=['left_at'])

        return Response({
            'ok': True,
            'challenge_id': ch.id,
            'cp_count': enrollment.cached_cp_count,
        }, status=status.HTTP_200_OK)


class ChallengeLeaveView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        tags=['04. Challenges'],
        operation_summary='Leave the active challenge enrollment')
    def post(self, request, pk):
        ch = get_object_or_404(Challenge, pk=pk)
        n = ChallengeParticipant.objects.filter(
            challenge=ch, user=request.user, left_at__isnull=True,
        ).update(left_at=timezone.now())
        return Response({'ok': True, 'left': n > 0})


class MyChallengeView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        tags=['04. Challenges'],
        operation_summary='Current active enrollment for the requesting user, optionally filtered by batch')
    def get(self, request):
        batch_id = request.query_params.get('batch_id')
        qs = ChallengeParticipant.objects.select_related('challenge', 'challenge__batch').filter(
            user=request.user, left_at__isnull=True,
        )
        enrollment = qs.first()
        if not enrollment:
            return Response({'enrolled': False})

        ch = enrollment.challenge
        # If a batch was specified, only return when challenge applies (general or matching).
        if batch_id:
            try:
                batch_id_int = int(batch_id)
            except (TypeError, ValueError):
                batch_id_int = None
            if ch.batch_id and ch.batch_id != batch_id_int:
                return Response({'enrolled': False, 'reason': 'challenge does not apply to this batch'})

        # Compute rank inline.
        better = ch.participants.filter(
            cached_cp_count__gt=enrollment.cached_cp_count,
        ).count()
        my_rank = better + 1

        # Top-1 (leader) for the banner — username + CP count.
        leader = (
            ch.participants
            .select_related('user')
            .order_by('-cached_cp_count', 'joined_at')
            .first()
        )
        leader_payload = None
        if leader:
            leader_payload = {
                'username': leader.user.username,
                'cp_count': leader.cached_cp_count,
                'is_you': leader.user_id == request.user.id,
            }

        return Response({
            'enrolled': True,
            'challenge': _serialize_challenge(ch, request.user),
            'my_cp': enrollment.cached_cp_count,
            'my_rank': my_rank,
            'leader': leader_payload,
            'participants_count': ch.participants.count(),
        })
