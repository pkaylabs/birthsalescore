from django.contrib import admin

from .models import *


@admin.register(ProductCategory)
class ProductCategoryAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'created_at')
    search_fields = ('name',)

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'vendor', 'price', 'category', 'in_stock', 'is_published')
    search_fields = ('name', 'vendor__vendor_name', 'category__name')

@admin.register(ProductImages)
class ProductImagesAdmin(admin.ModelAdmin):
    list_display = ('product', 'created_at')
    search_fields = ('product__name',)

@admin.register(ProductReview)
class ProductReviewAdmin(admin.ModelAdmin):
    list_display = ('product', 'user', 'rating', 'created_at')
    search_fields = ('product__name', 'user__vendor_name')

@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ('product', 'quantity', 'price')
    search_fields = ('product__name',)

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('user', 'total_price', 'status', 'payment_status', 'created_at')
    search_fields = ('user__name', 'status')

@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ('name', 'vendor', 'price', 'created_at')
    search_fields = ('name', 'vendor__vendor_name')

@admin.register(Ad)
class AdAdmin(admin.ModelAdmin):
    list_display = ('title', 'discounted_price', 'end_date')
    search_fields = ('title',)

@admin.register(AdImage)
class AdImageAdmin(admin.ModelAdmin):
    list_display = ('ad', 'created_at')
    search_fields = ('ad__title',)

@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('payment_id', 'order', 'user', 'amount', 'status', 'created_at')
    search_fields = ('payment_id', 'order__id', 'user__name')

@admin.register(ServiceBooking)
class ServiceBookingAdmin(admin.ModelAdmin):
    list_display = ('service', 'user', 'status', 'created_at',)
    search_fields = ('service', 'user',)

@admin.register(Banner)
class BannerAdmin(admin.ModelAdmin):
    list_display = ('title', 'link', 'is_active', 'created_at')
    search_fields = ('title', 'link')