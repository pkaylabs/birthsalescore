from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from drf_spectacular.utils import extend_schema, OpenApiExample, OpenApiResponse

from apis.models import DeliveryFee, Location
from apis.serializers import DeliveryFeeSerializer, LocationSerializer
from bscore.utils.permissions import IsAdminOnly


class LocationsAPIView(APIView):
    """Locations: public list; admin can create/update/delete."""

    @extend_schema(
        summary='List delivery locations (public)',
        responses={
            200: OpenApiResponse(
                description='List of locations',
                examples=[
                    OpenApiExample(
                        'Locations',
                        value=[
                            {
                                "id": 1,
                                "name": "Hall A",
                                "category": "HALL",
                                "delivery_fee_price": "5.00",
                                "created_at": "2026-02-20T00:00:00Z",
                                "updated_at": "2026-02-20T00:00:00Z",
                            }
                        ],
                    )
                ],
            )
        },
    )
    def get(self, request, *args, **kwargs):
        locations = Location.objects.all().order_by('category', 'name')
        # include fee price in response via LocationSerializer
        serializer = LocationSerializer(locations, many=True, context={"request": request})
        return Response(serializer.data, status=status.HTTP_200_OK)

    @extend_schema(
        summary='Create a delivery location (admin-only)',
        request={
            'application/json': {
                'type': 'object',
                'properties': {
                    'name': {'type': 'string'},
                    'category': {'type': 'string', 'enum': ['DEPARTMENT', 'HALL']},
                },
                'required': ['name', 'category'],
            }
        },
        responses={
            201: OpenApiResponse(description='Created'),
            401: OpenApiResponse(description='Authentication required'),
            403: OpenApiResponse(description='Only admins can create locations'),
            400: OpenApiResponse(description='Validation error'),
        },
        examples=[
            OpenApiExample('Create Location', value={"name": "Hall A", "category": "HALL"}, request_only=True),
        ],
    )
    def post(self, request, *args, **kwargs):
        if not (request.user and request.user.is_authenticated):
            return Response({"message": "Authentication required"}, status=status.HTTP_401_UNAUTHORIZED)
        if not IsAdminOnly().has_permission(request, self):
            return Response({"message": "Only admins can create locations"}, status=status.HTTP_403_FORBIDDEN)

        serializer = LocationSerializer(data=request.data, context={"request": request})
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @extend_schema(
        summary='Update a delivery location (admin-only)',
        request={
            'application/json': {
                'type': 'object',
                'properties': {
                    'id': {'type': 'integer'},
                    'location_id': {'type': 'integer'},
                    'name': {'type': 'string'},
                    'category': {'type': 'string', 'enum': ['DEPARTMENT', 'HALL']},
                },
            }
        },
        responses={
            200: OpenApiResponse(description='Updated'),
            401: OpenApiResponse(description='Authentication required'),
            403: OpenApiResponse(description='Only admins can update locations'),
            404: OpenApiResponse(description='Location not found'),
            400: OpenApiResponse(description='Validation error'),
        },
        examples=[
            OpenApiExample('Update Location', value={"id": 1, "name": "Hall A1"}, request_only=True),
        ],
    )
    def put(self, request, *args, **kwargs):
        if not (request.user and request.user.is_authenticated):
            return Response({"message": "Authentication required"}, status=status.HTTP_401_UNAUTHORIZED)
        if not IsAdminOnly().has_permission(request, self):
            return Response({"message": "Only admins can update locations"}, status=status.HTTP_403_FORBIDDEN)

        location_id = request.data.get('location_id') or request.data.get('id')
        if not location_id:
            return Response({"message": "location_id is required"}, status=status.HTTP_400_BAD_REQUEST)

        location = Location.objects.filter(id=location_id).first()
        if not location:
            return Response({"message": "Location not found"}, status=status.HTTP_404_NOT_FOUND)

        serializer = LocationSerializer(location, data=request.data, partial=True, context={"request": request})
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def patch(self, request, *args, **kwargs):
        return self.put(request, *args, **kwargs)

    @extend_schema(
        summary='Delete a delivery location (admin-only)',
        request={
            'application/json': {
                'type': 'object',
                'properties': {
                    'id': {'type': 'integer'},
                    'location_id': {'type': 'integer'},
                },
            }
        },
        responses={
            200: OpenApiResponse(description='Deleted'),
            401: OpenApiResponse(description='Authentication required'),
            403: OpenApiResponse(description='Only admins can delete locations'),
            404: OpenApiResponse(description='Location not found'),
            400: OpenApiResponse(description='Validation error'),
        },
        examples=[
            OpenApiExample('Delete Location', value={"id": 1}, request_only=True),
        ],
    )
    def delete(self, request, *args, **kwargs):
        if not (request.user and request.user.is_authenticated):
            return Response({"message": "Authentication required"}, status=status.HTTP_401_UNAUTHORIZED)
        if not IsAdminOnly().has_permission(request, self):
            return Response({"message": "Only admins can delete locations"}, status=status.HTTP_403_FORBIDDEN)

        location_id = request.data.get('location_id') or request.data.get('id')
        if not location_id:
            return Response({"message": "location_id is required"}, status=status.HTTP_400_BAD_REQUEST)

        location = Location.objects.filter(id=location_id).first()
        if not location:
            return Response({"message": "Location not found"}, status=status.HTTP_404_NOT_FOUND)

        location.delete()
        return Response({"message": "Location deleted successfully"}, status=status.HTTP_200_OK)


class DeliveryFeesAPIView(APIView):
    """Delivery fees: admin-only CRUD."""

    permission_classes = (permissions.IsAuthenticated, IsAdminOnly)

    @extend_schema(
        summary='List delivery fees (admin-only)',
        responses={
            200: OpenApiResponse(
                description='List of delivery fees',
                examples=[
                    OpenApiExample(
                        'Delivery Fees',
                        value=[
                            {
                                "id": 1,
                                "location": 1,
                                "location_name": "Hall A",
                                "location_category": "HALL",
                                "price": "5.00",
                                "created_at": "2026-02-20T00:00:00Z",
                                "updated_at": "2026-02-20T00:00:00Z",
                            }
                        ],
                    )
                ],
            )
        },
    )
    def get(self, request, *args, **kwargs):
        fees = DeliveryFee.objects.select_related('location').all().order_by('location__category', 'location__name')
        serializer = DeliveryFeeSerializer(fees, many=True, context={"request": request})
        return Response(serializer.data, status=status.HTTP_200_OK)

    @extend_schema(
        summary='Create a delivery fee (admin-only)',
        request={
            'application/json': {
                'type': 'object',
                'properties': {
                    'location': {'type': 'integer'},
                    'price': {'type': 'string'},
                },
                'required': ['location', 'price'],
            }
        },
        responses={
            201: OpenApiResponse(description='Created'),
            400: OpenApiResponse(description='Validation error'),
        },
        examples=[
            OpenApiExample('Create Fee', value={"location": 1, "price": "5.00"}, request_only=True),
        ],
    )
    def post(self, request, *args, **kwargs):
        serializer = DeliveryFeeSerializer(data=request.data, context={"request": request})
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @extend_schema(
        summary='Update a delivery fee (admin-only)',
        request={
            'application/json': {
                'type': 'object',
                'properties': {
                    'id': {'type': 'integer'},
                    'delivery_fee_id': {'type': 'integer'},
                    'location': {'type': 'integer'},
                    'price': {'type': 'string'},
                },
            }
        },
        responses={
            200: OpenApiResponse(description='Updated'),
            404: OpenApiResponse(description='Delivery fee not found'),
            400: OpenApiResponse(description='Validation error'),
        },
        examples=[
            OpenApiExample('Update Fee', value={"id": 1, "price": "6.00"}, request_only=True),
        ],
    )
    def put(self, request, *args, **kwargs):
        delivery_fee_id = request.data.get('delivery_fee_id') or request.data.get('id')
        if not delivery_fee_id:
            return Response({"message": "delivery_fee_id is required"}, status=status.HTTP_400_BAD_REQUEST)

        fee = DeliveryFee.objects.filter(id=delivery_fee_id).first()
        if not fee:
            return Response({"message": "Delivery fee not found"}, status=status.HTTP_404_NOT_FOUND)

        serializer = DeliveryFeeSerializer(fee, data=request.data, partial=True, context={"request": request})
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def patch(self, request, *args, **kwargs):
        return self.put(request, *args, **kwargs)

    @extend_schema(
        summary='Delete a delivery fee (admin-only)',
        request={
            'application/json': {
                'type': 'object',
                'properties': {
                    'id': {'type': 'integer'},
                    'delivery_fee_id': {'type': 'integer'},
                },
            }
        },
        responses={
            200: OpenApiResponse(description='Deleted'),
            404: OpenApiResponse(description='Delivery fee not found'),
            400: OpenApiResponse(description='Validation error'),
        },
        examples=[
            OpenApiExample('Delete Fee', value={"id": 1}, request_only=True),
        ],
    )
    def delete(self, request, *args, **kwargs):
        delivery_fee_id = request.data.get('delivery_fee_id') or request.data.get('id')
        if not delivery_fee_id:
            return Response({"message": "delivery_fee_id is required"}, status=status.HTTP_400_BAD_REQUEST)

        fee = DeliveryFee.objects.filter(id=delivery_fee_id).first()
        if not fee:
            return Response({"message": "Delivery fee not found"}, status=status.HTTP_404_NOT_FOUND)

        fee.delete()
        return Response({"message": "Delivery fee deleted successfully"}, status=status.HTTP_200_OK)
