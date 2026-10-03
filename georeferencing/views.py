from django.shortcuts import get_object_or_404
from django.utils import timezone

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from drf_yasg.utils import swagger_auto_schema
from rest_framework.parsers import JSONParser
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser, AllowAny
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
from django.db import models
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
            pending_geoattempts = GeoAttempt.objects.filter(status="PENDING")
        else:
            try:
                batch = Batch.objects.get(id=pk)
                pending_geoattempts = GeoAttempt.objects.filter(
                    status="PENDING", image__batch=batch,
                )
            except Batch.DoesNotExist:
                return Response({"error": "Batch not found."}, status=status.HTTP_404_NOT_FOUND)

        # Don't serve images that have already met their replica quota.
        # Image.replicas defines how many DONE attempts that image needs;
        # once reached, the remaining PENDING rows for it are wasted work.
        from django.db.models import Count
        covered_image_ids = (
            Image.objects
            .annotate(done_count=Count(
                'geoattempt', filter=models.Q(geoattempt__status='DONE'),
            ))
            .filter(done_count__gte=models.F('replicas'))
            .values_list('id', flat=True)
        )
        pending_geoattempts = pending_geoattempts.exclude(
            image_id__in=covered_image_ids,
        )

        # Avoid serving the same image twice to the same user. We exclude
        # any pending GeoAttempt whose Image already has a DONE attempt by
        # this user (in any other replica slot). Skipped tasks are not
        # tracked per-user yet, so a skipped image may reappear.
        if request.user.is_authenticated:
            done_image_ids = (
                GeoAttempt.objects
                .filter(assignedUser=request.user, status='DONE')
                .values_list('image_id', flat=True)
            )
            pending_geoattempts = pending_geoattempts.exclude(
                image_id__in=done_image_ids,
            )

        # Strict intersection: pending must satisfy the URL batch AND match
        # at least ONE active enrollment (UNION across the user's
        # challenges). Each enrollment's match condition is:
        # (challenge.batch matches OR challenge has no batch) AND
        # (image inside bbox if challenge has one).
        # Challenges without batch and without bbox don't restrict anything.
        challenge_filter_applied = False
        active_challenges_info = []
        if request.user.is_authenticated:
            now = timezone.now()
            active_enrollments = (
                ChallengeParticipant.objects
                .select_related('challenge')
                .filter(
                    user=request.user,
                    left_at__isnull=True,
                    challenge__is_paused=False,
                    challenge__start_at__lte=now,
                    challenge__end_at__gt=now,
                )
            )
            union_q = None
            for ep in active_enrollments:
                ch = ep.challenge
                applies = False
                ch_q = models.Q()
                if ch.batch_id:
                    ch_q &= models.Q(image__batch_id=ch.batch_id)
                    applies = True
                if ch.has_bbox:
                    ch_q &= ch.bbox_filter_q(
                        lat_field='image__photoCenterLat',
                        lon_field='image__photoCenterLon',
                    ) & models.Q(image__photoCenterLat__isnull=False)
                    applies = True
                if applies:
                    active_challenges_info.append({'id': ch.id, 'name': ch.name})
                    union_q = ch_q if union_q is None else (union_q | ch_q)
            if union_q is not None:
                pending_geoattempts = pending_geoattempts.filter(union_q)
                challenge_filter_applied = True

        # Check if any pending GeoAttempts exist
        if not pending_geoattempts.exists():
            if challenge_filter_applied:
                # Conflict: the active challenge(s) restricted the pool to 0.
                # Tell the client so it can prompt for the bypass.
                return Response({
                    "error": "No tasks match your active challenge(s) and the chosen batch.",
                    "challenge_conflict": True,
                    "challenges": active_challenges_info,
                }, status=status.HTTP_409_CONFLICT)
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

        # Personal stats for authenticated users (georeferencing.metrics:
        # ranks inside the verified population, ties share a rank).
        if request.user.is_authenticated:
            from . import metrics
            profile, _ = UserProfile.objects.get_or_create(user=request.user)
            r = metrics.all_ranks(profile)
            data['user_stats'] = {
                'tasks_done': r['tasks']['value'],
                'tasks_rank': r['tasks']['rank'],
                'tasks_to_next': r['tasks']['to_next'],
                'tasks_to_first': r['tasks']['to_first'],
                'control_points': r['cp']['value'],
                'cp_rank': r['cp']['rank'],
                'cp_to_next': r['cp']['to_next'],
                'cp_to_first': r['cp']['to_first'],
                'hours': round(r['time']['value'] / 3600, 1),
                'time_rank': r['time']['rank'],
                'time_to_next': round(r['time']['to_next'] / 3600, 1),
                'time_to_first': round(r['time']['to_first'] / 3600, 1),
            }

        return Response(data)


class GeoAttemptIndividualView(APIView):
    """
    API view for patching and deleting an image geo attempt.
    Methods:
    - patch: Patch an image geo attempt (anonymous OK — used during gettask flow).
    - delete: Delete an image geo attempt (admin only).
    """
    parser_classes = (JSONParser,)

    def get_permissions(self):
        # PATCH must work for anonymous users (gettask flow), but DELETE
        # is destructive and must be restricted to staff.
        if self.request.method == 'DELETE':
            return [IsAdminUser()]
        return [AllowAny()]
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
        # Accept both spellings for backwards compat with older clients.
        # Newer clients should send `control_points` only.
        control_points = (
            request.data.get('control_points')
            or request.data.get('controlPoints')
            or []
        )
        new_status = request.data.get('status')
        if new_status not in ('ASSIGNED', 'DONE', 'PENDING'):
            return Response({"error": "status must be ASSIGNED, DONE or PENDING"},
                            status=status.HTTP_400_BAD_REQUEST)

        # ── Ownership guard ──────────────────────────────────────────────
        # A task assigned to a user may only be changed by that user (or
        # staff). Anonymous callers may only touch anonymous tasks.
        owner_id = geoattemp.assignedUser_id
        if owner_id is not None and not request.user.is_staff and (
                not request.user.is_authenticated or request.user.id != owner_id):
            return Response({"error": "This task is assigned to another user."},
                            status=status.HTTP_403_FORBIDDEN)

        # ── State guard ──────────────────────────────────────────────────
        # Try / submit / skip only make sense while the task is ASSIGNED.
        # This makes DONE idempotent (a second submit is refused instead of
        # inflating counters) and stops "skip" from wiping a finished task
        # or a stale tab from submitting a task that was already released.
        if geoattemp.status != 'ASSIGNED':
            if geoattemp.status == 'DONE':
                msg = "This task was already submitted."
            else:
                msg = "This task is no longer assigned to you. Please load a new one."
            return Response({"error": msg, "task_status": geoattemp.status},
                            status=status.HTTP_409_CONFLICT)

        # A finished task without any control point is not a contribution.
        # (Seen in production: 'control_points': [] accepted as DONE.)
        if new_status == 'DONE' and not control_points:
            return Response({"error": "At least one control point is required to submit."},
                            status=status.HTTP_400_BAD_REQUEST)

        # The model field is `controlPoints`; make sure whatever spelling the
        # client used ends up stored (this mapping was missing between
        # 2026-05-02 and 2026-10-03 and every submit saved an empty list).
        data = dict(request.data)
        if control_points:
            data['controlPoints'] = control_points
        data.pop('control_points', None)
        serializer = GeoAttemptSerializer(geoattemp, data=data, partial=True)
        if serializer.is_valid():

            # We are receiving this status from user, so that means
            # that it's not finished yet, and the user is asking for
            # a new try
            if new_status == 'ASSIGNED':
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
                for item in control_points:
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
                mx = self.max_distance(control_points)
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
            elif new_status == 'DONE':
                # Clean up temporary tiles generated during Try
                tile_dir = 'media/georeferenced/' + geoattemp.image.name + geoattemp.hash
                tile_tif = tile_dir + '.tif'
                if os.path.exists(tile_tif):
                    os.remove(tile_tif)
                if os.path.exists(tile_dir):
                    shutil.rmtree(tile_dir)
                print('Submitting the final result')
                geoattemp.finishedDateTime = timezone.now()
                geoattemp.save()
                if geoattemp.assignedDateTime:
                    spend_time = (geoattemp.finishedDateTime -
                                  geoattemp.assignedDateTime).total_seconds()
                else:
                    spend_time = 0

                # Count exactly what will be persisted in `controlPoints`.
                cp_added = len(data.get('controlPoints') or [])
                user_profile = None
                enrollment = None

                # CHEATING CHECK FIRST — reject before touching any counters,
                # so that suspicious submits don't inflate stats / challenge
                # progress / daily streak.
                if spend_time < 10:
                    print('User is cheating')
                    geoattemp.finishedDateTime = None
                    geoattemp.save()
                    if geoattemp.assignedUser:
                        cheat_profile, _c = UserProfile.objects.get_or_create(
                            user=geoattemp.assignedUser)
                        cheat_profile.cheating += 1
                        cheat_profile.save()
                    return Response({"error": f"Are you cheating?. {spend_time}"}, status=status.HTTP_400_BAD_REQUEST)

                if geoattemp.assignedUser:
                    user_profile, created = UserProfile.objects.get_or_create(
                        user=geoattemp.assignedUser)
                    user_profile.geoattempts_done += 1
                    user_profile.time_spent += spend_time
                    user_profile.controlPointsDone += cp_added
                    user_profile.save()

                    # Challenge progress: if the user has an active enrollment
                    # whose challenge applies (active status + matching batch
                    # or general), add the submitted CPs to its cached counter.
                    if cp_added:
                        from django.db.models import F
                        now = timezone.now()
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
                            .first()
                        )
                        # The image must match the challenge (batch AND
                        # bbox) — same rule the task picker uses.
                        if enrollment and not enrollment.challenge.matching_images().filter(
                                pk=geoattemp.image_id).exists():
                            enrollment = None
                        if enrollment:
                            ChallengeParticipant.objects.filter(
                                pk=enrollment.pk,
                            ).update(cached_cp_count=F('cached_cp_count') + cp_added)

                    # Daily contribution counter
                    today = timezone.now().date()
                    geoattempts_today, created = GeoAttemptsByUserByDay.objects.get_or_create(
                        user=geoattemp.assignedUser, date=today,
                    )
                    geoattempts_today.numberGeoAttempts += 1
                    geoattempts_today.save()

                serializer.save()

                # ── Build the rich result payload for the post-submit overlay
                result = {
                    'delta': {
                        'cp': cp_added,
                        'tasks': 1,
                        'time_seconds': int(spend_time),
                    },
                    'image': {
                        'name': geoattemp.image.name,
                    },
                }
                if user_profile:
                    result['totals'] = {
                        'cp': user_profile.controlPointsDone,
                        'tasks': user_profile.geoattempts_done,
                        'time_seconds': int(user_profile.time_spent),
                    }
                    from . import metrics
                    prev_cp = max(user_profile.controlPointsDone - cp_added, 0)
                    result['rank'] = {
                        'global': metrics.global_rank(user_profile, 'cp')['rank'],
                        'previous_global': metrics.global_rank(user_profile, 'cp', value=prev_cp)['rank'],
                    }
                    result['streak_days'] = metrics.streak(geoattemp.assignedUser)[0]
                    # Challenge section (only if enrolled and CPs added)
                    if cp_added and enrollment is not None:
                        from django.db.models import Sum
                        fresh = (
                            ChallengeParticipant.objects
                            .select_related('challenge')
                            .get(pk=enrollment.pk)
                        )
                        ch = fresh.challenge
                        ahead_ch = ChallengeParticipant.objects.filter(
                            challenge=ch,
                            cached_cp_count__gt=fresh.cached_cp_count,
                        ).count()
                        prev_ahead_ch = ChallengeParticipant.objects.filter(
                            challenge=ch,
                            cached_cp_count__gt=max(fresh.cached_cp_count - cp_added, 0),
                        ).count()
                        total_cp_ch = ChallengeParticipant.objects.filter(
                            challenge=ch,
                        ).aggregate(total=Sum('cached_cp_count'))['total'] or 0
                        result['challenge'] = {
                            'id': ch.id,
                            'name': ch.name,
                            'added_cp': cp_added,
                            'my_cp': fresh.cached_cp_count,
                            'total_cp': total_cp_ch,
                            'target_bronze': ch.target_bronze,
                            'target_silver': ch.target_silver,
                            'target_gold': ch.target_gold,
                            'my_rank': ahead_ch + 1,
                            'previous_rank': prev_ahead_ch + 1,
                        }
                payload = dict(serializer.data)
                payload['result'] = result
                return Response(payload, status=status.HTTP_200_OK)

            # That means that the user click on "skip" button
            # So returning back to pending status
            elif new_status == 'PENDING':
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
        
        # Range: 12 months back from today up to the end of the current month.
        # (Computed with date arithmetic so Feb 29 and December do not crash.)
        today = timezone.now().date()
        start_date = datetime(today.year, today.month, today.day) - timedelta(days=365)
        first_next_month = (datetime(today.year + 1, 1, 1) if today.month == 12
                            else datetime(today.year, today.month + 1, 1))
        end_date = first_next_month - timedelta(days=1)
        
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


def _is_visible(user):
    """UserProfile.visible, defaulting to True when the profile is missing."""
    try:
        return bool(user.userprofile.visible)
    except UserProfile.DoesNotExist:
        return True


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
        leaderboard_qs = leaderboard_qs.select_related('user__userprofile')
        for i, p in enumerate(leaderboard_qs[:50], start=1):
            is_you = request.user.is_authenticated and p.user_id == request.user.id
            row = {
                'rank': i,
                # Invisible profiles keep their rank but not their name.
                'username': p.user.username if (_is_visible(p.user) or is_you) else None,
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

        # Nudge: how many CP separate me from the participant right above.
        my_gap = None
        if my_rank is not None and my_rank > 1:
            nxt = (ch.participants
                   .filter(cached_cp_count__gt=my_cp or 0)
                   .select_related('user')
                   .order_by('cached_cp_count')
                   .first())
            if nxt:
                my_gap = {
                    'cp_needed': nxt.cached_cp_count - (my_cp or 0) + 1,
                    'username': nxt.user.username if _is_visible(nxt.user) else None,
                }
        data['my_gap'] = my_gap
        return Response(data)


class ChallengeLeaderboardView(APIView):
    """
    Paginated per-challenge leaderboard.
    Query params:
      page:        1-based page number (default 1)
      page_size:   default 20, max 100
      jump_to_me:  '1' → return the page that contains the requesting user
    """
    permission_classes = [AllowAny]

    @swagger_auto_schema(
        tags=['04. Challenges'],
        operation_summary='Paginated leaderboard for a single challenge')
    def get(self, request, pk):
        ch = get_object_or_404(Challenge, pk=pk)

        try:
            page_size = max(1, min(100, int(request.GET.get('page_size', 20))))
        except (TypeError, ValueError):
            page_size = 20

        base = ch.participants.select_related('user', 'user__userprofile')
        total_users = base.count()
        total_pages = max(1, (total_users + page_size - 1) // page_size)

        my_rank = None
        my_cp = None
        my_username = None
        if request.user.is_authenticated:
            mine = base.filter(user=request.user).first()
            if mine:
                my_cp = mine.cached_cp_count
                my_rank = base.filter(
                    cached_cp_count__gt=mine.cached_cp_count,
                ).count() + 1
                my_username = request.user.username

        if request.GET.get('jump_to_me') == '1' and my_rank:
            page = ((my_rank - 1) // page_size) + 1
        else:
            try:
                page = max(1, int(request.GET.get('page', 1)))
            except (TypeError, ValueError):
                page = 1
        page = min(page, total_pages)

        offset = (page - 1) * page_size
        qs = base.order_by('-cached_cp_count', 'joined_at')[offset:offset + page_size]

        rows = []
        for i, p in enumerate(qs):
            rank = offset + i + 1
            up = getattr(p.user, 'userprofile', None)
            is_you = (request.user.is_authenticated and p.user_id == request.user.id)
            visible = bool(up.visible) if up is not None else True
            visible = visible or is_you
            rows.append({
                'rank': rank,
                'username': p.user.username if visible else None,
                'profile_pic_url': up.profile_pic.url if (visible and up and up.profile_pic) else None,
                'visible': visible,
                'is_you': is_you,
                'is_active': p.left_at is None,
                'cp_count': p.cached_cp_count,
                'joined_at': p.joined_at.isoformat() if p.joined_at else None,
                'left_at': p.left_at.isoformat() if p.left_at else None,
            })

        return Response({
            'challenge': {
                'id': ch.id,
                'name': ch.name,
            },
            'page': page,
            'page_size': page_size,
            'total_pages': total_pages,
            'total_users': total_users,
            'my_rank': my_rank,
            'my_cp': my_cp,
            'my_username': my_username,
            'rows': rows,
        })


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
            now = timezone.now()
            if other:
                other.left_at = now
                other.save(update_fields=['left_at'])
                other.close_periods(now)

            # Create or revive enrollment for the target challenge.
            enrollment, created = ChallengeParticipant.objects.select_for_update().get_or_create(
                challenge=ch, user=request.user,
            )
            if created:
                enrollment.start_period(enrollment.joined_at)
            elif enrollment.left_at is not None:
                enrollment.left_at = None
                enrollment.save(update_fields=['left_at'])
                enrollment.start_period(now)  # new stint; history kept

        return Response({
            'ok': True,
            'challenge': {
                'id': ch.id,
                'name': ch.name,
                'description': ch.description,
                'batch_id': ch.batch_id,
                'batch_name': ch.batch.name if ch.batch_id else None,
                'has_bbox': ch.has_bbox,
                'bbox': {
                    'min_lat': ch.bbox_min_lat, 'max_lat': ch.bbox_max_lat,
                    'min_lon': ch.bbox_min_lon, 'max_lon': ch.bbox_max_lon,
                } if ch.has_bbox else None,
                'target_bronze': ch.target_bronze,
                'target_silver': ch.target_silver,
                'target_gold': ch.target_gold,
                'cached_image_count': ch.cached_image_count,
                'cached_task_count': ch.cached_task_count,
            },
            'cp_count': enrollment.cached_cp_count,
            'replaced_other_enrollment': bool(other),
        }, status=status.HTTP_200_OK)


class ChallengeLeaveView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        tags=['04. Challenges'],
        operation_summary='Leave the active challenge enrollment')
    def post(self, request, pk):
        ch = get_object_or_404(Challenge, pk=pk)
        # Capture pre-leave CP count so we can tell the user "your N CPs are kept".
        existing = ChallengeParticipant.objects.filter(
            challenge=ch, user=request.user, left_at__isnull=True,
        ).first()
        cp_kept = existing.cached_cp_count if existing else 0
        now = timezone.now()
        n = ChallengeParticipant.objects.filter(
            challenge=ch, user=request.user, left_at__isnull=True,
        ).update(left_at=now)
        if existing:
            existing.close_periods(now)
        return Response({
            'ok': True,
            'left': n > 0,
            'challenge': {
                'id': ch.id,
                'name': ch.name,
            },
            'cp_count_kept': cp_kept,
        })


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
            is_you = leader.user_id == request.user.id
            leader_payload = {
                'username': leader.user.username if (_is_visible(leader.user) or is_you) else None,
                'cp_count': leader.cached_cp_count,
                'is_you': is_you,
            }

        return Response({
            'enrolled': True,
            'challenge': _serialize_challenge(ch, request.user),
            'my_cp': enrollment.cached_cp_count,
            'my_rank': my_rank,
            'leader': leader_payload,
            'participants_count': ch.participants.count(),
        })
