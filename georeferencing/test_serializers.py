from rest_framework.test import APITestCase
from georeferencing.serializers import ImageSerializer
from georeferencing.models import Image
from django.utils import timezone

class ImageSerializerTest(APITestCase):
    def setUp(self):
        self.image_attributes = {
            'name': 'test_image.jpg',
            'photoCenterByMachineLearning': 'center',
            'taken': timezone.now(),
            'focalLength': 35.0
        }
        self.image = Image.objects.create(**self.image_attributes)
        self.serializer = ImageSerializer(instance=self.image)

    def test_contains_expected_fields(self):
        data = self.serializer.data
        self.assertCountEqual(
            data.keys(),
            ['id', 'name', 'photoCenterByMachineLearning', 'taken', 'focalLength', 
            'createdDateTime', 'camera', 'cameraTilt', 'spacecraftNadirPoint', 
            'photoCenterPoint', 'spaceCraftAltitude', 'link', 'batch']
            )

    def test_name_field_content(self):
        data = self.serializer.data
        self.assertEqual(data['name'], self.image_attributes['name'])

    def test_photo_center_by_machine_learning_field_content(self):
        data = self.serializer.data
        self.assertEqual(data['photoCenterByMachineLearning'], self.image_attributes['photoCenterByMachineLearning'])

    def test_taken_field_content(self):
        data = self.serializer.data
        taken_utc = self.image_attributes['taken'].astimezone(timezone.utc).isoformat()

        self.assertEqual(data['taken'].replace('Z', '+00:00'), taken_utc)

    def test_focal_length_field_content(self):
        data = self.serializer.data
        self.assertEqual(data['focalLength'], self.image_attributes['focalLength'])