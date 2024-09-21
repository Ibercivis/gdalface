from django.shortcuts import get_object_or_404

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from drf_yasg.utils import swagger_auto_schema
from rest_framework.parsers import JSONParser
from .serializers import ControlpointSerializer, GeoAttemptSerializer, ImageSerializer, MiniGeoAttemptSerializer
from .models import Controlpoint, GeoAttempt, Image
import os
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
        pending_geoattempts = GeoAttempt.objects.filter(status="PENDING")

        if not pending_geoattempts.exists():
            return Response({"error": "No pending geo attempts found."}, status=status.HTTP_404_NOT_FOUND)

        # Select a random GeoAttempt
        geoattempt = random.choice(pending_geoattempts)

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
        serializer = GeoAttemptSerializer(geoattemp)
        return Response(serializer.data)
    
    @swagger_auto_schema(
            request_body=GeoAttemptSerializer,
            tags=['02. GeoAttempts'],
            operation_summary="Patch an image geo attempt")
    def patch(self, request, pk=None):
        geoattemp = get_object_or_404(GeoAttempt, pk=pk)
        serializer = GeoAttemptSerializer(gegeoattemp, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            if serializer.data['status'] == 'DOING':
                # let's start the georeferencing process
                # for the moment, launch a batch script
                print('doing georeferencing')
                command = 'gdal_translate -of GTiff'
                for controlpoint in geoattemp.controlpoint_set.all():
                    command += ' -gcp ' + str(controlpoint.x) + ' ' + str(controlpoint.y) + ' ' + str(controlpoint.lat) + ' ' + str(controlpoint.long)
                command += ' ' + geoattemp.image + ' ' + geoattemp
                print(command)
                
            return Response(serializer.data)
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
        images = Image.objects.all()
        serializer = ImageSerializer(images, many=True)
        return Response(serializer.data)
    
    @swagger_auto_schema(
            request_body=ImageSerializer,
            tags=['03. Images'],
            operation_summary="Post an image")
    def post(self, request):
        serializer = ImageSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        

class ImageIndividualView(APIView):
    @swagger_auto_schema(
            tags=['03. Images'],
            operation_summary="Get an image")
    def get(self, request, pk=None):
        image = get_object_or_404(Image, pk=pk)
        serializer = ImageSerializer(image)
        return Response(serializer.data)
    
    @swagger_auto_schema(
            request_body=ImageSerializer,
            tags=['03. Images'],
            operation_summary="Patch an image")
    def patch(self, request, pk=None):
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
        image = get_object_or_404(Image, pk=pk)
        image.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
