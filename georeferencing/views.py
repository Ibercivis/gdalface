from django.shortcuts import get_object_or_404
from django.utils import timezone

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from drf_yasg.utils import swagger_auto_schema
from rest_framework.parsers import JSONParser
from .serializers import ControlpointSerializer, GeoAttemptSerializer, ImageSerializer, MiniGeoAttemptSerializer
from .models import Controlpoint, GeoAttempt, Image
import os
import subprocess
import random



# Create your views here.

class ControlpointView(APIView):
    """
    ControlpointView class for managing control points.
    Attributes:
        parser_classes (tuple): Tuple of parser classes for request parsing.
    Methods:
        get(request): Get all control points.
        post(request): Post a control point.
    """
    parser_classes = (JSONParser,)

    @swagger_auto_schema(
            tags=['01. Controlpoints'],
            operation_summary="Get all control points")
    def get(self, request):
        controlpoints = Controlpoint.objects.all()
        serializer = ControlpointSerializer(controlpoints, many=True)
        return Response(serializer.data)
    
    @swagger_auto_schema(
            request_body=ControlpointSerializer,
            tags=['01. Controlpoints'],
            operation_summary="Post a control point")
    def post(self, request):
        serializer = ControlpointSerializer(data=request.data, context = {'request': request})
        
        if serializer.is_valid():
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    

class ControlpointIndividualView(APIView):
    """
    ControlpointIndividualView
    This class represents the API view for individual control points.
    Methods:
    - get: Retrieves a control point.
    - patch: Updates a control point.
    - delete: Deletes a control point.
    """
    parser_classes = (JSONParser,)

    @swagger_auto_schema(
            tags=['01. Controlpoints'],
            operation_summary="Get a control point")
    def get(self, request, pk=None):
        controlpoint = get_object_or_404(Controlpoint, pk=pk)
        serializer = ControlpointSerializer(controlpoint)
        return Response(serializer.data)
    
    @swagger_auto_schema(
            request_body=ControlpointSerializer,
            tags=['01. Controlpoints'],
            operation_summary="Patch a control point")
    def patch(self, request, pk=None):
        controlpoint = get_object_or_404(Controlpoint, pk=pk)
        serializer = ControlpointSerializer(controlpoint, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @swagger_auto_schema(
            tags=['01. Controlpoints'],
            operation_summary="Delete a control point")    
    def delete(self, request, pk=None):
        controlpoint = get_object_or_404(Controlpoint, pk=pk)
        controlpoint.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
    
    
class GeoAttemptView(APIView):
    """
    GeoAttemptView
    This class-based view handles the API endpoints for image geo attempts.
    Attributes:
        parser_classes (tuple): A tuple of parser classes used for request parsing.
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
        serializer = GeoAttemptSerializer(data=request.data, context = {'request': request})
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    

class PendingGeoAttemptView(APIView):
    """
    API view to retrieve a random GeoAttempt with a status of "PENDING".
    Methods:
    - get: Get a random "PENDING" GeoAttempt.
    """
    
    @swagger_auto_schema(
            tags=['02. GeoAttempts'],
            operation_summary="Get a random 'PENDING' geo attempt")
    def get(self, request):
        # Filter GeoAttempts by "PENDING" status
        print('Here')
        pending_geoattempts = GeoAttempt.objects.filter(status="PENDING")
        print(pending_geoattempts)
  

        if not pending_geoattempts.exists():
            print('No pending geo attempts found.')
            return Response({"error": "No pending geo attempts found."}, status=status.HTTP_404_NOT_FOUND)

        # Select a random GeoAttempt and initialize some fields
        geoattempt = random.choice(pending_geoattempts)
        geoattempt.status = 'ASSIGNED'
        geoattempt.assignedDateTime = timezone.now()
        geoattempt.finishedDateTime = None
        geoattempt.numberTries = 0
        geoattempt.controlPoints = []
        geoattempt.save()

        # Serialize the GeoAttempt
        serializer = GeoAttemptSerializer(geoattempt)

        # Return the serialized data
        return Response(serializer.data)
    

    
class GeoAttemptIndividualView(APIView):
    """
    API view for patching and deleting an image geo attempt.
    Methods:
    - patch: Patch an image geo attempt.
    - delete: Delete an image geo attempt.
    """
    parser_classes = (JSONParser,)

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
        serializer = GeoAttemptSerializer(geoattemp, data=request.data, partial=True)
        if serializer.is_valid():
        
            if request.data['status'] == 'ASSIGNED':
                print('Starting the testing process')
                # We increment the number of tries
                geoattemp.numberTries += 1
                geoattemp.save()

                # Ensure the georeferenced directory exists
                if not os.path.exists('media/georeferenced'):
                    os.makedirs('media/georeferenced')

                # First command: gdal_translate
                command = 'gdal_translate -of GTiff'
                for item in request.data['control_points']:
                    command += ' -gcp ' + str(item['actualPx']) + ' ' + str(item['actualPy'])
                    command += ' ' + str(item['lon']) + ' ' + str(item['lat'])
                command += ' media/original/' + geoattemp.image.name + '.JPG '
                command += ' media/georeferenced/' + geoattemp.image.name + geoattemp.hash + '.tif'
                print(command)
                try:
                    subprocess.run(command, shell=True, check=True, capture_output=True, text=True)
                except subprocess.CalledProcessError as e:
                    return Response({"error": f"gdal_translate failed: {e.stderr}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
                
                # Second command: gdalwarp
                # Check the # of points before enable tps (-order n to pylynomial)
                command = 'gdalwarp -r bilinear -tps -t_srs EPSG:4326'
                command += ' media/georeferenced/' + geoattemp.image.name + geoattemp.hash + '.tif'
                command += ' media/georeferenced/' + geoattemp.image.name + geoattemp.hash + '.tif'
                print(command)

                try:    
                    subprocess.run(command, shell=True, check=True, capture_output=True, text=True)
                except subprocess.CalledProcessError as e:
                    return Response({"error": f"gdalwarp failed: {e.stderr}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
                
                # Third command: Remove previous tiles
                command = 'rm -r media/georeferenced/' + geoattemp.image.name + geoattemp.hash
                print(command)
                if os.path.exists('media/georeferenced/' + geoattemp.image.name + geoattemp.hash):
                    try:
                        subprocess.run(command, shell=True, check=True, capture_output=True, text=True)
                    except subprocess.CalledProcessError as e:
                        return Response({"error": f"Failed to remove previous tiles: {e.stderr}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
               
                # Fourth command: (-r bilinear is slower, but....)
                command = 'gdal2tiles.py -z 7-12 -r near -s EPSG:4326'
                command += ' media/georeferenced/' + geoattemp.image.name + geoattemp.hash + '.tif'
                command += ' media/georeferenced/' + geoattemp.image.name + geoattemp.hash
                print(command)

                try:
                    subprocess.run(command, shell=True, capture_output=True, text=True)
                except subprocess.CalledProcessError as e:
                    return Response({"error": f"gdal2tiles failed: {e.stderr}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
              
                
            elif request.data['status'] == 'DONE':
                # let's start the georeferencing process
                # for the moment, launch a batch script
                print('doing georeferencing')
                print(request.data['controlPoints'])
                geoattemp.finishedDateTime = timezone.now()
                geoattemp.save()
                serializer.save()
            elif request.data['status'] == 'PENDING':
                # Come back to pending status
                print('Come back to pending status')
                # We are doing it mainly for control panel
                geoattemp.skipped += 1
                geoattemp.assignedDateTime = None
                geoattemp.finishedDateTime = None
                geoattemp.numberTries = 0
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
