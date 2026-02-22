from django.conf import settings
from django.utils import timezone
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apis.models import Banner, Product, ProductCategory, UserVideoAdState, VideoAd
from apis.serializers import (BannerSerializer, ProductCategorySerializer,
                              ProductSerializer)


def _maybe_get_video_ad_url(request):
    if not request.user.is_authenticated:
        return None

    interval = getattr(settings, 'VIDEO_AD_INTERVAL_SECONDS', 60)
    state, _ = UserVideoAdState.objects.get_or_create(user=request.user)
    now = timezone.now()

    if state.last_shown_at is not None:
        delta = (now - state.last_shown_at).total_seconds()
        if delta < interval:
            return None

    ad = VideoAd.objects.filter(is_active=True).order_by('?').first()
    if not ad:
        return None

    try:
        url = ad.video.url
    except Exception:
        return None

    state.last_shown_at = now
    state.save(update_fields=['last_shown_at', 'updated_at'])
    return request.build_absolute_uri(url)


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
        products = Product.objects.filter(is_published=True).order_by('?')[:30]
        best_selling_products = Product.objects.filter(is_published=True).order_by('?')[:10]
        new_arrivals = Product.objects.filter(is_published=True).order_by('-created_at')[:3]
        video_ad_url = _maybe_get_video_ad_url(request)
        response_data = {
            "banners": BannerSerializer(banners, many=True).data,
            "categories": ProductCategorySerializer(categories, many=True).data, 
            "products": ProductSerializer(products, many=True, context={"request": request}).data, 
            "best_selling_products": ProductSerializer(best_selling_products, many=True, context={"request": request}).data, 
            "new_arrivals": ProductSerializer(new_arrivals, many=True, context={"request": request}).data, 
            "video_ad_url": video_ad_url,
        }
        return Response(response_data, status=status.HTTP_200_OK)
