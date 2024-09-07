from rest_framework import serializers
from .models import Controlpoint, GeoAttempt, Image

class ControlpointSerializer(serializers.ModelSerializer):
    class Meta:
        model = Controlpoint
        fields = ['id', 'x', 'y', 'lat', 'long', 'created', 'geoAttempt']
        read_only_fields = ['created']

class GeoAttemptSerializer(serializers.ModelSerializer):
    class Meta:
        model = GeoAttempt
        fields = ['id', 'created', 'image', 'path', 'status', 'hash']
        read_only_fields = ['created', 'hash']

class MiniGeoAttemptSerializer(serializers.ModelSerializer):
    class Meta:
        model = GeoAttempt
        fields = ['id', 'created', 'image', 'status']
        read_only_fields = ['created']

class ImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Image
        fields = '__all__'