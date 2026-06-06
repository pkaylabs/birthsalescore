from decimal import Decimal, ROUND_HALF_UP

from django.db import IntegrityError, transaction
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import Vendor
from apis.models import (
    Product,
    VendorCustomerCoupon,
    VendorCustomerCouponRedemption,
    VendorPublishingCreditCoupon,
    VendorPublishingCreditRedemption,
)
from apis.serializers import (
    VendorCustomerCouponSerializer,
    VendorPublishingCreditCouponSerializer,
    VendorPublishingCreditRedemptionSerializer,
)
from bscore.utils.const import UserType


def _is_admin(user):
    return bool(user and (user.is_superuser or user.is_staff or user.user_type == UserType.ADMIN.value))


def _vendor_for_user(user):
    return Vendor.objects.filter(user=user).first()


class VendorPublishingCreditCouponAPIView(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    def get(self, request, *args, **kwargs):
        if not _is_admin(request.user):
            return Response({"message": "You are not allowed to access this page"}, status=status.HTTP_403_FORBIDDEN)
        coupons = VendorPublishingCreditCoupon.objects.all().order_by('-created_at')
        return Response(VendorPublishingCreditCouponSerializer(coupons, many=True).data, status=status.HTTP_200_OK)

    def post(self, request, *args, **kwargs):
        if not _is_admin(request.user):
            return Response({"message": "You are not allowed to access this page"}, status=status.HTTP_403_FORBIDDEN)
        serializer = VendorPublishingCreditCouponSerializer(data=request.data)
        if serializer.is_valid():
            coupon = serializer.save(created_by=request.user)
            return Response(
                {"message": "Publishing credit coupon created", "coupon": VendorPublishingCreditCouponSerializer(coupon).data},
                status=status.HTTP_201_CREATED,
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def put(self, request, *args, **kwargs):
        if not _is_admin(request.user):
            return Response({"message": "You are not allowed to access this page"}, status=status.HTTP_403_FORBIDDEN)
        coupon_id = request.data.get('coupon_id') or request.data.get('id')
        coupon = VendorPublishingCreditCoupon.objects.filter(id=coupon_id).first()
        if not coupon:
            return Response({"message": "Coupon not found"}, status=status.HTTP_404_NOT_FOUND)
        serializer = VendorPublishingCreditCouponSerializer(coupon, data=request.data, partial=True)
        if serializer.is_valid():
            coupon = serializer.save()
            return Response(
                {"message": "Publishing credit coupon updated", "coupon": VendorPublishingCreditCouponSerializer(coupon).data},
                status=status.HTTP_200_OK,
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, *args, **kwargs):
        if not _is_admin(request.user):
            return Response({"message": "You are not allowed to access this page"}, status=status.HTTP_403_FORBIDDEN)
        coupon_id = request.data.get('coupon_id') or request.data.get('id')
        coupon = VendorPublishingCreditCoupon.objects.filter(id=coupon_id).first()
        if not coupon:
            return Response({"message": "Coupon not found"}, status=status.HTTP_404_NOT_FOUND)
        coupon.delete()
        return Response({"message": "Publishing credit coupon deleted"}, status=status.HTTP_200_OK)


class RedeemPublishingCreditCouponAPIView(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    def post(self, request, *args, **kwargs):
        vendor = _vendor_for_user(request.user)
        if not vendor:
            return Response({"message": "Vendor profile not found"}, status=status.HTTP_400_BAD_REQUEST)

        code = str(request.data.get('code') or '').strip().upper()
        if not code:
            return Response({"message": "Coupon code is required"}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            coupon = VendorPublishingCreditCoupon.objects.select_for_update().filter(code=code).first()
            if not coupon:
                return Response({"message": "Coupon not found"}, status=status.HTTP_404_NOT_FOUND)
            if not coupon.redeemable:
                return Response({"message": "Coupon is expired, inactive, or fully redeemed"}, status=status.HTTP_400_BAD_REQUEST)
            if VendorPublishingCreditRedemption.objects.filter(vendor=vendor, coupon=coupon).exists():
                return Response({"message": "Coupon already redeemed by this vendor"}, status=status.HTTP_400_BAD_REQUEST)
            try:
                redemption = VendorPublishingCreditRedemption.objects.create(
                    vendor=vendor,
                    coupon=coupon,
                    product_credits=coupon.product_credits,
                    service_credits=coupon.service_credits,
                )
            except IntegrityError:
                return Response({"message": "Coupon already redeemed by this vendor"}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            {"message": "Coupon redeemed", "redemption": VendorPublishingCreditRedemptionSerializer(redemption).data},
            status=status.HTTP_201_CREATED,
        )


class VendorCustomerCouponAPIView(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    def get(self, request, *args, **kwargs):
        user = request.user
        if _is_admin(user):
            coupons = VendorCustomerCoupon.objects.select_related('vendor').all().order_by('-created_at')
        else:
            vendor = _vendor_for_user(user)
            if not vendor:
                return Response({"message": "Vendor profile not found"}, status=status.HTTP_400_BAD_REQUEST)
            coupons = VendorCustomerCoupon.objects.filter(vendor=vendor).order_by('-created_at')
        return Response(VendorCustomerCouponSerializer(coupons, many=True).data, status=status.HTTP_200_OK)

    def post(self, request, *args, **kwargs):
        vendor = _vendor_for_user(request.user)
        if not vendor:
            return Response({"message": "Vendor profile not found"}, status=status.HTTP_400_BAD_REQUEST)
        serializer = VendorCustomerCouponSerializer(data=request.data)
        if serializer.is_valid():
            coupon = serializer.save(vendor=vendor)
            return Response(
                {"message": "Customer discount coupon created", "coupon": VendorCustomerCouponSerializer(coupon).data},
                status=status.HTTP_201_CREATED,
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def put(self, request, *args, **kwargs):
        vendor = _vendor_for_user(request.user)
        coupon_id = request.data.get('coupon_id') or request.data.get('id')
        coupon = VendorCustomerCoupon.objects.filter(id=coupon_id).first()
        if not coupon:
            return Response({"message": "Coupon not found"}, status=status.HTTP_404_NOT_FOUND)
        if not _is_admin(request.user) and (not vendor or coupon.vendor_id != vendor.id):
            return Response({"message": "You are not allowed to update this coupon"}, status=status.HTTP_403_FORBIDDEN)
        serializer = VendorCustomerCouponSerializer(coupon, data=request.data, partial=True)
        if serializer.is_valid():
            coupon = serializer.save()
            return Response(
                {"message": "Customer discount coupon updated", "coupon": VendorCustomerCouponSerializer(coupon).data},
                status=status.HTTP_200_OK,
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, *args, **kwargs):
        vendor = _vendor_for_user(request.user)
        coupon_id = request.data.get('coupon_id') or request.data.get('id')
        coupon = VendorCustomerCoupon.objects.filter(id=coupon_id).first()
        if not coupon:
            return Response({"message": "Coupon not found"}, status=status.HTTP_404_NOT_FOUND)
        if not _is_admin(request.user) and (not vendor or coupon.vendor_id != vendor.id):
            return Response({"message": "You are not allowed to delete this coupon"}, status=status.HTTP_403_FORBIDDEN)
        coupon.delete()
        return Response({"message": "Customer discount coupon deleted"}, status=status.HTTP_200_OK)


class ValidateCustomerCouponAPIView(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    def post(self, request, *args, **kwargs):
        code = str(request.data.get('code') or '').strip().upper()
        items = request.data.get('items') or []
        if not code:
            return Response({"message": "Coupon code is required"}, status=status.HTTP_400_BAD_REQUEST)

        coupon = VendorCustomerCoupon.objects.select_related('vendor').filter(code=code).first()
        if not coupon:
            return Response({"message": "Coupon not found"}, status=status.HTTP_404_NOT_FOUND)
        if not coupon.redeemable:
            return Response({"message": "Coupon is expired, inactive, or fully redeemed"}, status=status.HTTP_400_BAD_REQUEST)
        if VendorCustomerCouponRedemption.objects.filter(coupon=coupon, customer=request.user).count() >= coupon.per_customer_limit:
            return Response({"message": "You have already used this coupon"}, status=status.HTTP_400_BAD_REQUEST)

        eligible_subtotal = Decimal('0.00')
        for item in items:
            product = Product.objects.filter(id=item.get('product')).select_related('vendor').first()
            if not product or product.vendor_id != coupon.vendor_id:
                continue
            quantity = int(item.get('quantity') or 1)
            eligible_subtotal += Decimal(product.price) * Decimal(quantity)

        if eligible_subtotal <= 0:
            return Response({"message": "Coupon is not valid for these products"}, status=status.HTTP_400_BAD_REQUEST)
        if eligible_subtotal < Decimal(coupon.minimum_order_amount):
            return Response(
                {"message": f"Minimum eligible order amount is {coupon.minimum_order_amount}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if coupon.discount_type == 'PERCENTAGE':
            discount_amount = (eligible_subtotal * Decimal(coupon.discount_value) / Decimal('100')).quantize(
                Decimal('0.01'), rounding=ROUND_HALF_UP
            )
        else:
            discount_amount = min(Decimal(coupon.discount_value), eligible_subtotal)

        return Response(
            {
                "message": "Coupon is valid",
                "coupon": VendorCustomerCouponSerializer(coupon).data,
                "eligible_subtotal": str(eligible_subtotal),
                "discount_amount": str(discount_amount),
            },
            status=status.HTTP_200_OK,
        )
