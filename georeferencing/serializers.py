from rest_framework import serializers
from .models import Controlpoint, GeoAttempt, Image

class ControlpointSerializer(serializers.ModelSerializer):
    class Meta:
        model = Controlpoint
        fields = ['id', 'x', 'y', 'lat', 'long', 'created', 'geoAttempt']
        read_only_fields = ['created']

class GeoAttemptSerializer(serializers.ModelSerializer):
    image_name = serializers.SerializerMethodField()
    photo_center_by_machine_learning = serializers.SerializerMethodField()
    photo_taken = serializers.SerializerMethodField()
    focal_length = serializers.SerializerMethodField()

    class Meta:
        model = GeoAttempt
        fields = ['id', 
                  'created',
                  'image',
                  'image_name',
                  'photo_center_by_machine_learning',
                  'status',
                  'hash',
                  'skipped',
                  'controlPoints',
                  'photo_taken',
                  'focal_length']
        read_only_fields = ['created', 'hash']

    def get_image_name(self, obj):
        return obj.image.name
    
    def get_photo_center_by_machine_learning(self, obj):
        return obj.image.photoCenterByMachineLearning
    
    def get_photo_taken(self,obj):
        return obj.image.taken
    
    def get_focal_length(self, obj):
        return obj.image.focalLength
    
class MiniGeoAttemptSerializer(serializers.ModelSerializer):
    class Meta:
        model = GeoAttempt
        fields = ['id', 'created', 'image', 'status']
        read_only_fields = ['created']

class ImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Image
        fields = '__all__'