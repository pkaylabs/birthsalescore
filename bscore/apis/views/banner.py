from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apis.models import Banner
from apis.serializers import BannerSerializer
from bscore.utils.const import UserType


class BannerAPIView(APIView):
    '''API Endpoints for managing banners'''

    permission_classes = (permissions.IsAuthenticated,)

    def get(self, request, *args, **kwargs):
        '''Retrieve all banners'''
        # only admin users can access this endpoint
        user = request.user
        if not user.is_superuser and not user.is_staff and user.user_type != UserType.ADMIN.value:
            return Response({"message": "You don't have permission to access this"}, status=status.HTTP_403_FORBIDDEN)
        banners = Banner.objects.all().order_by('-created_at')
        serializer = BannerSerializer(banners, many=True, context={"request": request})
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request, *args, **kwargs):
        '''Create a new banner'''
        user = request.user
        if not user.is_superuser and not user.is_staff and user.user_type != UserType.ADMIN.value:
            return Response({"message": "You don't have permission to access this"}, status=status.HTTP_403_FORBIDDEN)
        serializer = BannerSerializer(data=request.data, context={"request": request})
        if serializer.is_valid():
            serializer.save()
            return Response({"message": "Banner Created Successfully", "banner": serializer.data}, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    def put(self, request, *args, **kwargs):
        '''Update an existing banner'''
        user = request.user
        if not user.is_superuser and not user.is_staff and user.user_type != UserType.ADMIN.value:
            return Response({"message": "You don't have permission to access this"}, status=status.HTTP_403_FORBIDDEN)
        banner_id = request.data.get('banner')
        if not banner_id:
            return Response({"message": "Banner ID is required"}, status=status.HTTP_400_BAD_REQUEST)
        
        banner = Banner.objects.filter(id=banner_id).first()
        if not banner:
            return Response({"message": "Banner not found"}, status=status.HTTP_404_NOT_FOUND)
        
        serializer = BannerSerializer(banner, data=request.data, partial=True, context={"request": request})
        if serializer.is_valid():
            serializer.save()
            return Response({"message": "Banner Updated Successfully", "banner": serializer.data}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    def delete(self, request, *args, **kwargs):
        '''Delete a banner'''
        user = request.user
        if not user.is_superuser and not user.is_staff and user.user_type != UserType.ADMIN.value:
            return Response({"message": "You don't have permission to access this"}, status=status.HTTP_403_FORBIDDEN)
        banner_id = request.data.get('banner')
        if not banner_id:
            return Response({"message": "Banner ID is required"}, status=status.HTTP_400_BAD_REQUEST)
        
        banner = Banner.objects.filter(id=banner_id).first()
        if not banner:
            return Response({"message": "Banner not found"}, status=status.HTTP_404_NOT_FOUND)
        
        banner.delete()
        return Response({"message": "Banner Deleted Successfully"}, status=status.HTTP_200_OK)