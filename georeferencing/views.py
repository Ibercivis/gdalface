from django.shortcuts import get_object_or_404
from django.utils import timezone

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from drf_yasg.utils import swagger_auto_schema
from rest_framework.parsers import JSONParser
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated  # Add this import
from .serializers import GeoAttemptSerializer, ImageSerializer, MiniGeoAttemptSerializer
from .models import GeoAttempt, Image, Batch, GeoAttemptsByUserByDay
from user_profile.models import UserProfile
import os
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
        return Response(serializer.data)


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
                command = 'gdalwarp -r bilinear -tps -t_srs EPSG:4326'
                command += ' media/georeferenced/' + \
                    geoattemp.image.name + geoattemp.hash + '.tif'
                command += ' media/georeferenced/' + \
                    geoattemp.image.name + geoattemp.hash + '.tif'
                print(command)

                try:
                    subprocess.run(command, shell=True, check=True,
                                   capture_output=True, text=True)
                except subprocess.CalledProcessError as e:
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
