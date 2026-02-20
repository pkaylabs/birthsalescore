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
        summary='Add an extra product image (vendor/admin)',
        request={
            'multipart/form-data': {
                'type': 'object',
                'properties': {
                    'image': {'type': 'string', 'format': 'binary'},
                },
                'required': ['image'],
            }
        },
        responses={
            201: ProductImagesSerializer,
            400: OpenApiResponse(description='Validation error'),
            401: OpenApiResponse(description='Authentication required'),
            403: OpenApiResponse(description='Not allowed'),
            404: OpenApiResponse(description='Product not found'),
        },
        examples=[
            OpenApiExample(
                'Upload Extra Image',
                value={"image": "(binary)"},
                request_only=True,
            ),
        ],
    )
    def post(self, request, product_id: int, *args, **kwargs):
        product = self._get_product(product_id=product_id)
        if not product:
            return Response({"message": "Product not found"}, status=status.HTTP_404_NOT_FOUND)

        if not self._can_manage(request, product):
            return Response({"message": "Not allowed"}, status=status.HTTP_403_FORBIDDEN)

        serializer = ProductImagesSerializer(data=request.data, context={"request": request})
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        obj = serializer.save(product=product)
        return Response(ProductImagesSerializer(obj, context={"request": request}).data, status=status.HTTP_201_CREATED)

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

        image.delete()
        return Response({"message": "Image deleted successfully"}, status=status.HTTP_200_OK)
