from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

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

    def post(self, request, *args, **kwargs):
        serializer = VideoAdSerializer(data=request.data, context={"request": request})
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

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

    def delete(self, request, *args, **kwargs):
        video_ad_id = request.data.get('video_ad_id') or request.data.get('id')
        if not video_ad_id:
            return Response({"message": "video_ad_id is required"}, status=status.HTTP_400_BAD_REQUEST)

        ad = VideoAd.objects.filter(id=video_ad_id).first()
        if not ad:
            return Response({"message": "Video ad not found"}, status=status.HTTP_404_NOT_FOUND)

        ad.delete()
        return Response({"message": "Video ad deleted successfully"}, status=status.HTTP_200_OK)
