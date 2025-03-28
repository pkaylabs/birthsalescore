from django.contrib import admin

from .models import *

admin.site.site_header = 'BIRTHSALES PORTAL'

# user
@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ('name', 'email', 'phone', 'user_type','is_staff', 'is_superuser')
    search_fields = ('name', 'email', 'phone',)

@admin.register(Wallet)
class WalletAdmin(admin.ModelAdmin):
    list_display = ('wallet_id', 'vendor', 'balance', 'created_at', 'updated_at')
    search_fields = ('wallet_id', )

# otp
@admin.register(OTP)
class OTPAdmin(admin.ModelAdmin):
    list_display = ('phone', 'otp', 'created_at', 'updated_at')
    search_fields = ('phone', 'otp',)

# vendor
@admin.register(Vendor)
class VendorAdmin(admin.ModelAdmin):
    list_display = ('vendor_id', 'vendor_name', 'vendor_phone', 'created_at', 'updated_at')
    search_fields = ('vendor_id', 'vendor_name', 'vendor_phone',)

