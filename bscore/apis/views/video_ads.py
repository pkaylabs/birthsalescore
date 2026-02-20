from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from drf_spectacular.utils import OpenApiExample, OpenApiResponse, extend_schema

from apis.models import VideoAd
from apis.serializers import VideoAdSerializer
from bscore.utils.permissions import IsAdminOnly


class VideoAdAPIView(APIView):
    """Admin CRUD for video advertisements."""

    permission_classes = (permissions.IsAuthenticated, IsAdminOnly)

    def get(self, request, *args, **kwargs):
        ads = VideoAd.objects.all().order_by('-created_at')
        serializer = VideoAdSerializer(ads, many=True, context={"request": request})
        return Response(serializer.data, status=status.HTTP_200_OK)

    @extend_schema(
        summary='Create a video ad (admin-only)',
        request=VideoAdSerializer,
        responses={
            201: VideoAdSerializer,
            400: OpenApiResponse(description='Validation error'),
            401: OpenApiResponse(description='Authentication required'),
            403: OpenApiResponse(description='Only admins can create video ads'),
        },
        examples=[
            OpenApiExample(
                'Create Video Ad',
                value={
                    "title": "Homepage Promo",
                    "is_active": True,
                    "video": "promo.mp4",
                },
                request_only=True,
            ),
            OpenApiExample(
                'Video Ad Response',
                value={
                    "id": 1,
                    "title": "Homepage Promo",
                    "video": "http://localhost:8000/media/video_ads/promo.mp4",
                    "is_active": True,
                    "created_at": "2026-02-20T12:00:00Z",
                    "updated_at": "2026-02-20T12:00:00Z",
                },
                response_only=True,
            ),
        ],
    )
    def post(self, request, *args, **kwargs):
        serializer = VideoAdSerializer(data=request.data, context={"request": request})
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @extend_schema(
        summary='Update a video ad (admin-only)',
        request=VideoAdSerializer,
        responses={
            200: VideoAdSerializer,
            400: OpenApiResponse(description='Validation error'),
            401: OpenApiResponse(description='Authentication required'),
            403: OpenApiResponse(description='Only admins can update video ads'),
            404: OpenApiResponse(description='Video ad not found'),
        },
        examples=[
            OpenApiExample(
                'Update Video Ad',
                value={
                    "id": 1,
                    "title": "Homepage Promo (Updated)",
                    "is_active": False,
                },
                request_only=True,
            ),
        ],
    )
    def put(self, request, *args, **kwargs):
        video_ad_id = request.data.get('video_ad_id') or request.data.get('id')
        if not video_ad_id:
            return Response({"message": "video_ad_id is required"}, status=status.HTTP_400_BAD_REQUEST)

        ad = VideoAd.objects.filter(id=video_ad_id).first()
        if not ad:
            return Response({"message": "Video ad not found"}, status=status.HTTP_404_NOT_FOUND)

        serializer = VideoAdSerializer(ad, data=request.data, partial=True, context={"request": request})
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def patch(self, request, *args, **kwargs):
        return self.put(request, *args, **kwargs)

    @extend_schema(
        summary='Delete a video ad (admin-only)',
        request={
            'application/json': {
                'type': 'object',
                'properties': {
                    'id': {'type': 'integer'},
                    'video_ad_id': {'type': 'integer'},
                },
            }
        },
        responses={
            200: OpenApiResponse(description='Deleted'),
            400: OpenApiResponse(description='Validation error'),
            401: OpenApiResponse(description='Authentication required'),
            403: OpenApiResponse(description='Only admins can delete video ads'),
            404: OpenApiResponse(description='Video ad not found'),
        },
        examples=[
            OpenApiExample('Delete Video Ad', value={"id": 1}, request_only=True),
        ],
    )
    def delete(self, request, *args, **kwargs):
        video_ad_id = request.data.get('video_ad_id') or request.data.get('id')
        if not video_ad_id:
            return Response({"message": "video_ad_id is required"}, status=status.HTTP_400_BAD_REQUEST)

        ad = VideoAd.objects.filter(id=video_ad_id).first()
        if not ad:
            return Response({"message": "Video ad not found"}, status=status.HTTP_404_NOT_FOUND)

        ad.delete()
        return Response({"message": "Video ad deleted successfully"}, status=status.HTTP_200_OK)
