from django.urls import path
import apis.views as views

app_name = 'apis'
urlpatterns = [
    path('', views.HealthCheckAPIView.as_view(), name='ping'),
]

# accounts and users
urlpatterns += [
    path('login/', views.LoginAPI.as_view(), name='login'),
    path('verify-otp/', views.VerifyOTPAPI.as_view(), name='verify_otp'),
    path('register/', views.RegisterAPI.as_view(), name='register_user'),
    
]