from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apis.models import Location
from apis.serializers import LocationSerializer


class MobileLocationsAPIView(APIView):
    """Public list of delivery locations for mobile clients."""

    def get(self, request, *args, **kwargs):
        locations = Location.objects.all().order_by('category', 'name')
        serializer = LocationSerializer(locations, many=True, context={"request": request})
        return Response(serializer.data, status=status.HTTP_200_OK)
