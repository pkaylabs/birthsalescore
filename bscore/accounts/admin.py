from django.contrib import admin

from .models import *

admin.site.site_header = 'BIRTHSALES PORTAL'

# user
@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ('name', 'email', 'phone', 'user_type','is_staff', 'is_superuser')
    search_fields = ('name', 'email', 'phone',)

# otp
@admin.register(OTP)
class OTPAdmin(admin.ModelAdmin):
    list_display = ('phone', 'otp', 'created_at', 'updated_at')
    search_fields = ('phone', 'otp',)

