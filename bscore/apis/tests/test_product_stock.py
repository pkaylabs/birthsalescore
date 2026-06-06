from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import Subscription, SubscriptionPackage, User, Vendor
from apis.models import Location, Payment, Product, ProductCategory
from bscore.utils.const import PaymentStatus, PaymentStatusCode, UserType


class ProductStockTests(TestCase):
    def setUp(self):
        self.client = APIClient()

        self.customer = User.objects.create_user(
            email="customer-stock@example.com",
            phone="233000001001",
            name="Stock Customer",
            password="Password123!",
            user_type=UserType.CUSTOMER.value,
            phone_verified=True,
            email_verified=True,
        )

        vendor_user = User.objects.create_user(
            email="vendor-stock@example.com",
            phone="233000001002",
            name="Stock Vendor",
            password="Password123!",
            user_type=UserType.VENDOR.value,
            phone_verified=True,
            email_verified=True,
        )
        self.vendor = Vendor.objects.create(
            user=vendor_user,
            vendor_name="Stock Shop",
            vendor_phone="233500001002",
            vendor_email="vendor-stock-shop@example.com",
            vendor_address="Accra",
        )
        package = SubscriptionPackage.objects.create(
            package_name="Stock Pro",
            package_description="Stock package",
            package_price=Decimal("10.00"),
            can_create_product=True,
            can_create_service=True,
        )
        subscription = Subscription.objects.create(
            vendor=self.vendor,
            package=package,
            start_date=timezone.localdate() - timedelta(days=1),
            end_date=timezone.localdate() + timedelta(days=30),
        )
        Payment.objects.create(
            subscription=subscription,
            user=vendor_user,
            amount=package.package_price,
            status=PaymentStatus.SUCCESS.value,
            status_code=PaymentStatusCode.SUCCESS.value,
        )

        self.category = ProductCategory.objects.create(name="Stocked")
        self.product = Product.objects.create(
            name="Tracked Product",
            description="Quantity is tracked",
            price=Decimal("12.00"),
            category=self.category,
            is_published=True,
            vendor=self.vendor,
            stock_quantity=3,
        )
        self.location = Location.objects.create(name="Accra", category="City")

    @patch("apis.models.Order.notify_vendor_and_customer")
    def test_order_deducts_stock_and_rejects_oversell(self, _mock_notify):
        self.client.force_authenticate(user=self.customer)
        url = reverse("apis:place_order")

        response = self.client.post(
            url,
            data={
                "items": [{"product": self.product.id, "quantity": 2}],
                "location": str(self.location.id),
                "customer_phone": "233501234567",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)

        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 1)
        self.assertTrue(self.product.in_stock)

        response = self.client.post(
            url,
            data={
                "items": [{"product": self.product.id, "quantity": 2}],
                "location": str(self.location.id),
                "customer_phone": "233501234567",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400)

        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 1)
