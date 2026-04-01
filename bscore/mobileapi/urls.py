from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .viewsets import (
	BannerViewSet,
	CategoryViewSet,
	MobileHomepageAPIView,
	MobileMyBookingsAPIView,
	ProductViewSet,
	ServiceViewSet,
)
from .auth import (
	MobileForgotPasswordRequestOTPAPI,
	MobileForgotPasswordResetAPI,
	MobileForgotPasswordVerifyOTPAPI,
	MobileLoginAPI,
	MobileRegisterAPI,
	MobileVerifyOTPAPI,
	MobileUserProfileAPIView,
	MobileChangePasswordAPI,
	MobileContactSupportAPI,
	MobileUserAvatarUpdateAPI,
)
from knox.views import LogoutView, LogoutAllView
from .locations import MobileLocationsAPIView

app_name = 'mobileapi'

router = DefaultRouter()
router.register(r'products', ProductViewSet, basename='mobile-products')
router.register(r'services', ServiceViewSet, basename='mobile-services')
router.register(r'categories', CategoryViewSet, basename='mobile-categories')
router.register(r'banners', BannerViewSet, basename='mobile-banners')

urlpatterns = [
	path('homepage/', MobileHomepageAPIView.as_view(), name='homepage'),
	path('locations/', MobileLocationsAPIView.as_view(), name='locations'),
	path('bookings/', MobileMyBookingsAPIView.as_view(), name='my_bookings'),
	# Auth endpoints
	path('login/', MobileLoginAPI.as_view(), name='login'),
	path('register/', MobileRegisterAPI.as_view(), name='register'),
	path('verifyotp/', MobileVerifyOTPAPI.as_view(), name='verify_otp'),
	# Forgot password flow
	path('forgotpassword/otp/', MobileForgotPasswordRequestOTPAPI.as_view(), name='forgot_password_otp'),
	path('forgotpassword/verify/', MobileForgotPasswordVerifyOTPAPI.as_view(), name='forgot_password_verify_otp'),
	path('forgotpassword/reset/', MobileForgotPasswordResetAPI.as_view(), name='forgot_password_reset'),
	path('profile/', MobileUserProfileAPIView.as_view(), name='profile'),
	path('changepassword/', MobileChangePasswordAPI.as_view(), name='change_password'),
	path('contactsupport/', MobileContactSupportAPI.as_view(), name='contact_support'),
	path('profile/avatar/', MobileUserAvatarUpdateAPI.as_view(), name='profile_avatar_update'),
	# Logout only current token
	path('logout/', LogoutView.as_view(), name='logout_current'),
	# Logout all tokens for the user
	path('logout-all/', LogoutAllView.as_view(), name='logout_all'),
	path('', include(router.urls)),
]
