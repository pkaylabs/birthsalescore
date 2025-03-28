from django.urls import path
import apis.views as views

app_name = 'apis'
urlpatterns = [
    path('/', views.HealthCheckAPIView.as_view(), name='ping'),
]
