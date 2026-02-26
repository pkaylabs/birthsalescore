from rest_framework import permissions, status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from drf_spectacular.utils import OpenApiExample, OpenApiResponse, extend_schema

from accounts.models import Vendor
from apis.models import Service, ServiceImages
from apis.serializers import ServiceImagesSerializer
from apis.utils.querysets import filter_services_for_public
from bscore.utils.const import UserType
from bscore.utils.permissions import IsAdminOnly


class ServiceExtraImagesAPIView(APIView):
    """Nested CRUD for extra service images.

    - GET  /services/{service_id}/images/ -> list images
    - POST /services/{service_id}/images/ -> add image (multipart)
    - DELETE /services/{service_id}/images/{image_id}/ -> delete image

    Viewing (GET): public for services that are publicly viewable.
    Managing (POST/DELETE): vendor who owns the service, or admin/staff.
    """

    permission_classes = (permissions.AllowAny,)
    parser_classes = (MultiPartParser, FormParser)

    def get_permissions(self):
        if self.request.method == 'GET':
            return [permissions.AllowAny()]
        return [permissions.IsAuthenticated()]

    def _get_service(self, *, service_id: int):
        return Service.objects.filter(id=service_id).select_related('vendor').first()

    def _can_manage(self, request, service: Service) -> bool:
        if not service:
            return False

        user = request.user
        if not (user and user.is_authenticated):
            return False

        if user.is_superuser or IsAdminOnly().has_permission(request, self):
            return True

        if getattr(user, 'user_type', None) != UserType.VENDOR.value:
            return False

        vendor = Vendor.objects.filter(user=user).first()
        if not vendor:
            return False

        if not (vendor.has_active_subscription() and vendor.can_create_or_view_service()):
            return False

        return service.vendor_id == vendor.id

    @extend_schema(
        summary='List extra images for a service (public)',
        responses={
            200: ServiceImagesSerializer(many=True),
            404: OpenApiResponse(description='Service not found'),
        },
    )
    def get(self, request, service_id: int, *args, **kwargs):
        service = self._get_service(service_id=service_id)
        if not service:
            return Response({"message": "Service not found"}, status=status.HTTP_404_NOT_FOUND)

        # Allow vendor/admin to view even if unpublished.
        if not self._can_manage(request, service):
            public_service = filter_services_for_public(Service.objects.filter(id=service_id, published=True)).first()
            if not public_service:
                return Response({"message": "Service not found"}, status=status.HTTP_404_NOT_FOUND)

        images = ServiceImages.objects.filter(service_id=service_id).order_by('-created_at')
        serializer = ServiceImagesSerializer(images, many=True, context={"request": request})
        return Response(serializer.data, status=status.HTTP_200_OK)

    @extend_schema(
        summary='Add extra service images (vendor/admin)',
        request={
            'multipart/form-data': {
                'type': 'object',
                'properties': {
                    'image': {
                        'type': 'string',
                        'format': 'binary',
                        'description': 'Single file (backwards compatible). You can also repeat this field multiple times.',
                    },
                    'images': {
                        'type': 'array',
                        'items': {'type': 'string', 'format': 'binary'},
                        'description': 'Upload multiple files in one request (max 7 total extra images per service)',
                    },
                },
            }
        },
        responses={
            201: ServiceImagesSerializer(many=True),
            400: OpenApiResponse(description='Validation error'),
            401: OpenApiResponse(description='Authentication required'),
            403: OpenApiResponse(description='Not allowed'),
            404: OpenApiResponse(description='Service not found'),
        },
        examples=[
            OpenApiExample(
                'Upload Extra Images',
                value={"images": ["(binary)", "(binary)"]},
                request_only=True,
            ),
            OpenApiExample(
                'Upload Single Extra Image',
                value={"image": "(binary)"},
                request_only=True,
            ),
            OpenApiExample(
                'Upload Response (list)',
                value=[
                    {
                        "id": 201,
                        "service": 1,
                        "image": "http://localhost:8000/media/service_images/img1.jpg",
                        "created_at": "2026-02-20T12:00:00Z",
                        "updated_at": "2026-02-20T12:00:00Z",
                    },
                    {
                        "id": 202,
                        "service": 1,
                        "image": "http://localhost:8000/media/service_images/img2.jpg",
                        "created_at": "2026-02-20T12:00:00Z",
                        "updated_at": "2026-02-20T12:00:00Z",
                    },
                ],
                response_only=True,
            ),
        ],
    )
    def post(self, request, service_id: int, *args, **kwargs):
        service = self._get_service(service_id=service_id)
        if not service:
            return Response({"message": "Service not found"}, status=status.HTTP_404_NOT_FOUND)

        if not self._can_manage(request, service):
            return Response({"message": "Not allowed"}, status=status.HTTP_403_FORBIDDEN)

        # Accept either a single file field `image` or multiple via `images` (or repeated `image`).
        files = request.FILES.getlist('images')
        if not files:
            files = request.FILES.getlist('image')

        if not files:
            return Response({"message": "image or images is required"}, status=status.HTTP_400_BAD_REQUEST)

        if len(files) > 7:
            return Response({"message": "Maximum 7 images allowed"}, status=status.HTTP_400_BAD_REQUEST)

        existing_count = ServiceImages.objects.filter(service_id=service_id).count()
        if existing_count + len(files) > 7:
            return Response(
                {
                    "message": "Maximum 7 images allowed per service",
                    "existing_count": existing_count,
                    "attempted_upload": len(files),
                    "max_allowed": 7,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        created = []
        for f in files:
            obj = ServiceImages.objects.create(service=service, image=f)
            created.append(obj)

        return Response(
            ServiceImagesSerializer(created, many=True, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )

    @extend_schema(
        summary='Delete an extra service image (vendor/admin)',
        responses={
            200: OpenApiResponse(description='Deleted'),
            401: OpenApiResponse(description='Authentication required'),
            403: OpenApiResponse(description='Not allowed'),
            404: OpenApiResponse(description='Service or image not found'),
        },
    )
    def delete(self, request, service_id: int, image_id: int = None, *args, **kwargs):
        if image_id is None:
            return Response({"message": "image_id is required"}, status=status.HTTP_400_BAD_REQUEST)

        service = self._get_service(service_id=service_id)
        if not service:
            return Response({"message": "Service not found"}, status=status.HTTP_404_NOT_FOUND)

        if not self._can_manage(request, service):
            return Response({"message": "Not allowed"}, status=status.HTTP_403_FORBIDDEN)

        image = ServiceImages.objects.filter(id=image_id, service_id=service_id).first()
        if not image:
            return Response({"message": "Image not found"}, status=status.HTTP_404_NOT_FOUND)

        try:
            if getattr(image, 'image', None):
                image.image.delete(save=False)
        except Exception:
            pass

        image.delete()
        return Response({"message": "Image deleted successfully"}, status=status.HTTP_200_OK)
