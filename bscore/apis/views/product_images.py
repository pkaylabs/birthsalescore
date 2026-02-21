from rest_framework import permissions, status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from drf_spectacular.utils import OpenApiExample, OpenApiResponse, extend_schema

from accounts.models import Vendor
from apis.models import Product, ProductImages
from apis.serializers import ProductImagesSerializer
from bscore.utils.const import UserType
from bscore.utils.permissions import IsAdminOnly


class ProductExtraImagesAPIView(APIView):
    """Nested CRUD for extra product images.

    - GET  /products/{product_id}/images/ -> list images
    - POST /products/{product_id}/images/ -> add image (multipart)
    - DELETE /products/{product_id}/images/{image_id}/ -> delete image

    Allowed: vendor who owns the product, or admin/staff.
    """

    permission_classes = (permissions.IsAuthenticated,)
    parser_classes = (MultiPartParser, FormParser)

    def _get_product(self, *, product_id: int):
        return Product.objects.filter(id=product_id).select_related('vendor').first()

    def _can_manage(self, request, product: Product) -> bool:
        if not product:
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

        if not (vendor.has_active_subscription() and vendor.can_create_or_view_product()):
            return False

        return product.vendor_id == vendor.id

    @extend_schema(
        summary='List extra images for a product (vendor/admin)',
        responses={
            200: ProductImagesSerializer(many=True),
            401: OpenApiResponse(description='Authentication required'),
            403: OpenApiResponse(description='Not allowed'),
            404: OpenApiResponse(description='Product not found'),
        },
    )
    def get(self, request, product_id: int, *args, **kwargs):
        product = self._get_product(product_id=product_id)
        if not product:
            return Response({"message": "Product not found"}, status=status.HTTP_404_NOT_FOUND)

        if not self._can_manage(request, product):
            return Response({"message": "Not allowed"}, status=status.HTTP_403_FORBIDDEN)

        images = ProductImages.objects.filter(product_id=product_id).order_by('-created_at')
        serializer = ProductImagesSerializer(images, many=True, context={"request": request})
        return Response(serializer.data, status=status.HTTP_200_OK)

    @extend_schema(
        summary='Add extra product images (vendor/admin)',
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
                        'description': 'Upload multiple files in one request (max 7 total extra images per product)',
                    },
                },
            }
        },
        responses={
            201: ProductImagesSerializer(many=True),
            400: OpenApiResponse(description='Validation error'),
            401: OpenApiResponse(description='Authentication required'),
            403: OpenApiResponse(description='Not allowed'),
            404: OpenApiResponse(description='Product not found'),
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
                        "id": 101,
                        "product": 1,
                        "image": "http://localhost:8000/media/product_images/img1.jpg",
                        "created_at": "2026-02-20T12:00:00Z",
                        "updated_at": "2026-02-20T12:00:00Z",
                    },
                    {
                        "id": 102,
                        "product": 1,
                        "image": "http://localhost:8000/media/product_images/img2.jpg",
                        "created_at": "2026-02-20T12:00:00Z",
                        "updated_at": "2026-02-20T12:00:00Z",
                    },
                ],
                response_only=True,
            ),
        ],
    )
    def post(self, request, product_id: int, *args, **kwargs):
        product = self._get_product(product_id=product_id)
        if not product:
            return Response({"message": "Product not found"}, status=status.HTTP_404_NOT_FOUND)

        if not self._can_manage(request, product):
            return Response({"message": "Not allowed"}, status=status.HTTP_403_FORBIDDEN)

        # Accept either a single file field `image` or multiple via `images` (or repeated `image`).
        files = request.FILES.getlist('images')
        if not files:
            files = request.FILES.getlist('image')

        if not files:
            return Response({"message": "image or images is required"}, status=status.HTTP_400_BAD_REQUEST)

        if len(files) > 7:
            return Response({"message": "Maximum 7 images allowed"}, status=status.HTTP_400_BAD_REQUEST)

        existing_count = ProductImages.objects.filter(product_id=product_id).count()
        if existing_count + len(files) > 7:
            return Response(
                {
                    "message": "Maximum 7 images allowed per product",
                    "existing_count": existing_count,
                    "attempted_upload": len(files),
                    "max_allowed": 7,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        created = []
        for f in files:
            obj = ProductImages.objects.create(product=product, image=f)
            created.append(obj)

        return Response(
            ProductImagesSerializer(created, many=True, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )

    @extend_schema(
        summary='Delete an extra product image (vendor/admin)',
        responses={
            200: OpenApiResponse(description='Deleted'),
            401: OpenApiResponse(description='Authentication required'),
            403: OpenApiResponse(description='Not allowed'),
            404: OpenApiResponse(description='Product or image not found'),
        },
    )
    def delete(self, request, product_id: int, image_id: int = None, *args, **kwargs):
        if image_id is None:
            return Response({"message": "image_id is required"}, status=status.HTTP_400_BAD_REQUEST)

        product = self._get_product(product_id=product_id)
        if not product:
            return Response({"message": "Product not found"}, status=status.HTTP_404_NOT_FOUND)

        if not self._can_manage(request, product):
            return Response({"message": "Not allowed"}, status=status.HTTP_403_FORBIDDEN)

        image = ProductImages.objects.filter(id=image_id, product_id=product_id).first()
        if not image:
            return Response({"message": "Image not found"}, status=status.HTTP_404_NOT_FOUND)

        # Ensure the underlying file is removed from storage as well.
        try:
            if getattr(image, 'image', None):
                image.image.delete(save=False)
        except Exception:
            pass

        image.delete()
        return Response({"message": "Image deleted successfully"}, status=status.HTTP_200_OK)
