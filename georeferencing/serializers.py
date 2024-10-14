from rest_framework import serializers
from .models import GeoAttempt, Image

class GeoAttemptSerializer(serializers.ModelSerializer):
    """
    GeoAttemptSerializer is a Django REST framework serializer for the GeoAttempt model. 
    It serializes the following fields: 'id', 'created', 'image', 'image_name', 
    'photo_center_by_machine_learning', 'status', 'hash', 'skipped', 'controlPoints', 
    'photo_taken', and 'focal_length'. The 'created' and 'hash' fields are read-only.
    Attributes:
        image_name (str): The name of the image associated with the GeoAttempt.
        photo_center_by_machine_learning (str): The photo center determined by machine learning.
        photo_taken (datetime): The date and time when the photo was taken.
        focal_length (float): The focal length of the camera used to take the photo.
    Methods:
        get_image_name(obj): Returns the name of the image associated with the GeoAttempt.
        get_photo_center_by_machine_learning(obj): Returns the photo center determined by machine learning.
        get_photo_taken(obj): Returns the date and time when the photo was taken.
        get_focal_length(obj): Returns the focal length of the camera used to take the photo.
    """
    image_name = serializers.SerializerMethodField()
    photo_center_by_machine_learning = serializers.SerializerMethodField()
    photo_center_point = serializers.SerializerMethodField()
    photo_taken = serializers.SerializerMethodField()
    focal_length = serializers.SerializerMethodField()

    class Meta:
        model = GeoAttempt
        fields = ['id', 
                  'assignedUser',
                  'createdDateTime',
                  'assignedDateTime',
                  'finishedDateTime',
                  'numberTries',
                  'image',
                  'image_name',
                  'photo_center_point',
                  'photo_center_by_machine_learning',
                  'status',
                  'hash',
                  'skipped',
                  'controlPoints',
                  'photo_taken',
                  'focal_length']
        read_only_fields = ['createdDateTime', 'hash']

    def get_image_name(self, obj):
        return obj.image.name
    
    def get_photo_center_point(self, obj):
        return obj.image.photoCenterPoint
    
    def get_photo_center_by_machine_learning(self, obj):
        return obj.image.photoCenterByMachineLearning
    
    def get_photo_taken(self,obj):
        return obj.image.taken
    
    def get_focal_length(self, obj):
        return obj.image.focalLength
    
class MiniGeoAttemptSerializer(serializers.ModelSerializer):
    """
    Serializer for the GeoAttempt model, providing a minimal set of fields.

    This serializer includes the following fields:
    - id: The unique identifier for the GeoAttempt instance.
    - created: The timestamp when the GeoAttempt instance was created. This field is read-only.
    - image: The image associated with the GeoAttempt instance.
    - status: The current status of the GeoAttempt instance.

    Meta:
        model: The model class that this serializer is based on (GeoAttempt).
        fields: The list of fields to include in the serialized representation.
        read_only_fields: The list of fields that should be read-only.
    """
    class Meta:
        model = GeoAttempt
        fields = ['id', 'created', 'image', 'status']
        read_only_fields = ['created']

class ImageSerializer(serializers.ModelSerializer):
    """
    Serializer for the Image model.

    This serializer converts Image model instances into JSON format and vice versa.
    It includes all fields of the Image model.

    Attributes:
        Meta (class): A nested class that defines the metadata options for the serializer.
            model (Image): The model that this serializer is associated with.
            fields (str): Specifies that all fields of the model should be included in the serialization.
    """
    class Meta:
        model = Image
        fields = '__all__'