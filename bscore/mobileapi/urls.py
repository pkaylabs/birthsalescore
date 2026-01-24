from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .viewsets import (
	BannerViewSet,
	CategoryViewSet,
	MobileHomepageAPIView,
	ProductViewSet,
	ServiceViewSet,
)
from .auth import (
	MobileLoginAPI,
	MobileRegisterAPI,
	MobileVerifyOTPAPI,
)
from knox.views import LogoutView, LogoutAllView

app_name = 'mobileapi'

router = DefaultRouter()
router.register(r'products', ProductViewSet, basename='mobile-products')
router.register(r'services', ServiceViewSet, basename='mobile-services')
router.register(r'categories', CategoryViewSet, basename='mobile-categories')
router.register(r'banners', BannerViewSet, basename='mobile-banners')

urlpatterns = [
	path('homepage/', MobileHomepageAPIView.as_view(), name='homepage'),
	# Auth endpoints
	path('login/', MobileLoginAPI.as_view(), name='login'),
	path('register/', MobileRegisterAPI.as_view(), name='register'),
	path('verifyotp/', MobileVerifyOTPAPI.as_view(), name='verify_otp'),
	# Logout only current token
	path('logout/', LogoutView.as_view(), name='logout_current'),
	# Logout all tokens for the user
	path('logout-all/', LogoutAllView.as_view(), name='logout_all'),
	path('', include(router.urls)),
]
