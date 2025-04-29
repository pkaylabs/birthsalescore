from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apis.models import Banner, Product, ProductCategory
from apis.serializers import (BannerSerializer, ProductCategorySerializer,
                              ProductSerializer)


class HealthCheckAPIView(APIView):
    """
    A simple health check view to verify that the API is running.
    """

    permission_classes = [permissions.AllowAny]

    def get(self, request, *args, **kwargs):
        """
        Returns a 200 OK response with a message indicating that the API is healthy.
        """
        return Response(
            {"status": "ok", "message": "API is healthy"}, status=status.HTTP_200_OK
        )
    


class HomepageAPIView(APIView):
    """
    View for the eCommerce homepage.
    """

    permission_classes = [permissions.AllowAny]

    def get(self, request, *args, **kwargs):
        """
        Returns the homepage data including banners, categories, products, etc.
        """
        banners = Banner.objects.filter(is_active=True).order_by('?')[:10]
        categories = ProductCategory.objects.all().order_by('-created_at')
        products = Product.objects.filter(is_published=True).order_by('?')[:10]
        best_selling_products = Product.objects.filter(is_published=True).order_by('?')[:10]
        new_arrivals = Product.objects.filter(is_published=True).order_by('-created_at')[:3]
        response_data = {
            "banners": BannerSerializer(banners, many=True).data,
            "categories": ProductCategorySerializer(categories, many=True).data, 
            "products": ProductSerializer(products, many=True).data, 
            "best_selling_products": ProductSerializer(best_selling_products, many=True).data, 
            "new_arrivals": ProductSerializer(new_arrivals, many=True).data, 
        }
        return Response(response_data, status=status.HTTP_200_OK)
