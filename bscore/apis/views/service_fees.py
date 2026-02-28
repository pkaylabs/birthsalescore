from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from drf_spectacular.utils import OpenApiExample, OpenApiResponse, extend_schema

from apis.models import ServiceFee
from apis.serializers import ServiceFeeSerializer
from bscore.utils.permissions import IsAdminOnly


class ServiceFeesAPIView(APIView):
    """Service fees: admin-only CRUD.

    This config is systemwide (not tied to locations/vendors).
    """

    permission_classes = (permissions.IsAuthenticated, IsAdminOnly)

    @extend_schema(
        summary='List service fees (admin-only)',
        responses={
            200: ServiceFeeSerializer(many=True),
        },
        examples=[
            OpenApiExample(
                'List Service Fees (Response)',
                value=[
                    {
                        'id': 2,
                        'fee_type': 'PERCENTAGE',
                        'value': '5.00',
                        'is_active': True,
                        'created_at': '2026-02-28T10:00:00Z',
                        'updated_at': '2026-02-28T10:00:00Z',
                    },
                    {
                        'id': 1,
                        'fee_type': 'FLAT',
                        'value': '2.50',
                        'is_active': False,
                        'created_at': '2026-02-01T10:00:00Z',
                        'updated_at': '2026-02-01T10:00:00Z',
                    },
                ],
                response_only=True,
            ),
        ],
    )
    def get(self, request, *args, **kwargs):
        fees = ServiceFee.objects.all().order_by('-is_active', '-created_at')
        serializer = ServiceFeeSerializer(fees, many=True, context={"request": request})
        return Response(serializer.data, status=status.HTTP_200_OK)

    @extend_schema(
        summary='Create a service fee (admin-only)',
        request=ServiceFeeSerializer,
        responses={
            201: ServiceFeeSerializer,
            400: OpenApiResponse(description='Validation error'),
        },
        examples=[
            OpenApiExample('Create Percentage Fee', value={"fee_type": "PERCENTAGE", "value": "5.00", "is_active": True}, request_only=True),
            OpenApiExample('Create Flat Fee', value={"fee_type": "FLAT", "value": "2.50", "is_active": True}, request_only=True),
        ],
    )
    def post(self, request, *args, **kwargs):
        serializer = ServiceFeeSerializer(data=request.data, context={"request": request})
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @extend_schema(
        summary='Update a service fee (admin-only)',
        request=ServiceFeeSerializer,
        responses={
            200: ServiceFeeSerializer,
            404: OpenApiResponse(description='Service fee not found'),
            400: OpenApiResponse(description='Validation error'),
        },
        examples=[
            OpenApiExample('Update Fee', value={"id": 1, "value": "6.00"}, request_only=True),
            OpenApiExample('Activate Fee', value={"id": 1, "is_active": True}, request_only=True),
        ],
    )
    def put(self, request, *args, **kwargs):
        service_fee_id = request.data.get('service_fee_id') or request.data.get('id')
        if not service_fee_id:
            return Response({"message": "service_fee_id is required"}, status=status.HTTP_400_BAD_REQUEST)

        fee = ServiceFee.objects.filter(id=service_fee_id).first()
        if not fee:
            return Response({"message": "Service fee not found"}, status=status.HTTP_404_NOT_FOUND)

        serializer = ServiceFeeSerializer(fee, data=request.data, partial=True, context={"request": request})
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def patch(self, request, *args, **kwargs):
        return self.put(request, *args, **kwargs)

    @extend_schema(
        summary='Delete a service fee (admin-only)',
        request={
            'application/json': {
                'type': 'object',
                'properties': {
                    'id': {'type': 'integer'},
                    'service_fee_id': {'type': 'integer'},
                },
            }
        },
        responses={
            200: OpenApiResponse(description='Deleted'),
            404: OpenApiResponse(description='Service fee not found'),
            400: OpenApiResponse(description='Validation error'),
        },
        examples=[
            OpenApiExample('Delete Fee', value={"id": 1}, request_only=True),
        ],
    )
    def delete(self, request, *args, **kwargs):
        service_fee_id = request.data.get('service_fee_id') or request.data.get('id')
        if not service_fee_id:
            return Response({"message": "service_fee_id is required"}, status=status.HTTP_400_BAD_REQUEST)

        fee = ServiceFee.objects.filter(id=service_fee_id).first()
        if not fee:
            return Response({"message": "Service fee not found"}, status=status.HTTP_404_NOT_FOUND)

        fee.delete()
        return Response({"message": "Service fee deleted successfully"}, status=status.HTTP_200_OK)
