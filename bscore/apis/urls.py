from django.urls import path

import apis.views as views

app_name = 'apis'
urlpatterns = [
    path('', views.HealthCheckAPIView.as_view(), name='ping'),
]

# accounts and users
urlpatterns += [
    path('homepage/', views.HomepageAPIView.as_view(), name='homepage'),
    path('login/', views.LoginAPI.as_view(), name='login'),
    path('verifyotp/', views.VerifyOTPAPI.as_view(), name='verify_otp'),
    path('register/', views.RegisterAPI.as_view(), name='register_user'),
    path('userprofile/', views.UserProfileAPIView.as_view(), name='profile'),
    path('changepassword/', views.ChangePasswordAPIView.as_view(), name='change_password'), 
    path('resetpassword/', views.ResetPasswordAPIView.as_view(), name='reset_password'),
    path('users/', views.UsersAPIView.as_view(), name='users'),
    path('services/', views.ServicesAPIView.as_view(), name='services'),
    path('bookings/', views.BookingsAPIView.as_view(), name='bookings'),
    path('vendors/', views.VendorsAPIView.as_view(), name='vendors'),
    path('vendorprofile/', views.VendorProfileAPIView.as_view(), name='vendorprofile'),
    path('subscriptionpackage/', views.SubscriptionPackageAPIView.as_view(), name='sub_package'),
    path('subscriptions/', views.SubscriptionAPIView.as_view(), name='subscriptions'),
    path('dashboard/', views.DashboardAPIView.as_view(), name='dashboard'),
    path('products/', views.ProductAPIView.as_view(), name='products'),
    path('productcategory/', views.ProductCategoryAPIView.as_view(), name='category'),
    path('placeorder/', views.PlaceOrderAPIView.as_view(), name='place_order'),
    path('orders/', views.OrderAPIView.as_view(), name='orders'),
]