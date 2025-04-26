from django.contrib import admin

from .models import *

admin.site.site_header = 'BIRTHNON ADMIN PORTAL'

# user
@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ('name', 'email', 'phone', 'user_type','is_staff', 'is_superuser')
    search_fields = ('name', 'email', 'phone',)

@admin.register(Vendor)
class VendorAdmin(admin.ModelAdmin):
    list_display = ('vendor_name', 'vendor_email', 'vendor_phone', 'vendor_id')
    search_fields = ('vendor_name', 'vendor_email', 'vendor_phone', 'vendor_id')

@admin.register(SubscriptionPackage)
class SubscriptionPackageAdmin(admin.ModelAdmin):
    list_display = ('package_name', 'package_price')
    search_fields = ('package_name',)

@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ('vendor', 'package', 'start_date', 'end_date')
    search_fields = ('vendor__vendor_name', 'package__package_name')

@admin.register(Wallet)
class WalletAdmin(admin.ModelAdmin):
    list_display = ('wallet_id', 'vendor', 'balance')
    search_fields = ('wallet_id', 'vendor__vendor_name')

@admin.register(OTP)
class OTPAdmin(admin.ModelAdmin):
    list_display = ('phone', 'otp', 'created_at')
    search_fields = ('phone', 'otp')

