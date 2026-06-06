from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import Subscription, SubscriptionPackage, User, Vendor
from apis.models import (
    Location,
    Payment,
    Product,
    ProductCategory,
    VendorCustomerCoupon,
    VendorCustomerCouponRedemption,
    VendorPublishingCreditCoupon,
)
from bscore.utils.const import PaymentStatus, PaymentStatusCode, UserType


class CouponTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_superuser(
            email="coupon-admin@example.com",
            phone="233000002001",
            name="Coupon Admin",
            password="Password123!",
            user_type=UserType.ADMIN.value,
        )
        self.customer = User.objects.create_user(
            email="coupon-customer@example.com",
            phone="233000002002",
            name="Coupon Customer",
            password="Password123!",
            user_type=UserType.CUSTOMER.value,
            phone_verified=True,
            email_verified=True,
        )
        self.vendor_user = User.objects.create_user(
            email="coupon-vendor@example.com",
            phone="233000002003",
            name="Coupon Vendor",
            password="Password123!",
            user_type=UserType.VENDOR.value,
            phone_verified=True,
            email_verified=True,
        )
        self.vendor = Vendor.objects.create(
            user=self.vendor_user,
            vendor_name="Coupon Shop",
            vendor_phone="233500002003",
            vendor_email="coupon-shop@example.com",
            vendor_address="Accra",
        )
        self.package = SubscriptionPackage.objects.create(
            package_name="Coupon Basic",
            package_description="Coupon package",
            package_price=Decimal("10.00"),
            can_create_product=True,
            can_create_service=True,
            max_products=1,
            max_services=0,
        )
        subscription = Subscription.objects.create(
            vendor=self.vendor,
            package=self.package,
            start_date=timezone.localdate() - timedelta(days=1),
            end_date=timezone.localdate() + timedelta(days=30),
        )
        Payment.objects.create(
            subscription=subscription,
            user=self.vendor_user,
            amount=self.package.package_price,
            status=PaymentStatus.SUCCESS.value,
            status_code=PaymentStatusCode.SUCCESS.value,
        )
        self.category = ProductCategory.objects.create(name="Coupon Products")
        self.product = Product.objects.create(
            name="Coupon Product",
            description="Discountable product",
            price=Decimal("100.00"),
            category=self.category,
            is_published=True,
            vendor=self.vendor,
            stock_quantity=5,
        )
        self.location = Location.objects.create(name="Coupon City", category="City")

    def test_vendor_redeems_admin_credit_coupon_to_extend_limit(self):
        self.assertFalse(self.vendor.can_create_more_products())

        coupon = VendorPublishingCreditCoupon.objects.create(
            code="MOREPRODUCTS",
            credit_type="PRODUCT",
            product_credits=1,
            max_redemptions=1,
            created_by=self.admin,
        )

        self.client.force_authenticate(user=self.vendor_user)
        response = self.client.post(
            reverse("apis:redeem_publishing_credit_coupon"),
            data={"code": coupon.code},
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertTrue(self.vendor.can_create_more_products())

    @patch("apis.models.Order.notify_vendor_and_customer")
    def test_customer_coupon_discount_is_saved_on_order(self, _mock_notify):
        coupon = VendorCustomerCoupon.objects.create(
            code="SAVE10",
            vendor=self.vendor,
            discount_type="PERCENTAGE",
            discount_value=Decimal("10.00"),
            max_redemptions=2,
            per_customer_limit=1,
            minimum_order_amount=Decimal("50.00"),
        )

        self.client.force_authenticate(user=self.customer)
        response = self.client.post(
            reverse("apis:place_order"),
            data={
                "items": [{"product": self.product.id, "quantity": 1}],
                "location": str(self.location.id),
                "customer_phone": "233501234567",
                "coupon_code": coupon.code,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        order_id = response.json()["data"]["id"]
        redemption = VendorCustomerCouponRedemption.objects.get(order_id=order_id)
        self.assertEqual(redemption.discount_amount, Decimal("10.00"))
        self.assertEqual(redemption.coupon, coupon)

        order_total = Decimal(str(response.json()["data"]["total_amount"]))
        self.assertEqual(order_total, Decimal("90.00"))
