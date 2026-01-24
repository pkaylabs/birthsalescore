from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .viewsets import (
	BannerViewSet,
	CategoryViewSet,
	MobileHomepageAPIView,
	ProductViewSet,
	ServiceViewSet,
)

app_name = 'mobileapi'

router = DefaultRouter()
router.register(r'products', ProductViewSet, basename='mobile-products')
router.register(r'services', ServiceViewSet, basename='mobile-services')
router.register(r'categories', CategoryViewSet, basename='mobile-categories')
router.register(r'banners', BannerViewSet, basename='mobile-banners')

urlpatterns = [
	path('homepage/', MobileHomepageAPIView.as_view(), name='homepage'),
	path('', include(router.urls)),
]
