from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import Subscription, SubscriptionPackage, User, Vendor
from apis.models import Product, ProductCategory
from bscore.utils.const import UserType


class PublicAccessTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_anonymous_can_list_product_categories(self):
        ProductCategory.objects.create(name="Diapers")
        ProductCategory.objects.create(name="Clothes")

        url = reverse("apis:category")
        resp = self.client.get(url)

        self.assertEqual(resp.status_code, 200)
        self.assertIsInstance(resp.json(), list)
        self.assertGreaterEqual(len(resp.json()), 2)

    def test_homepage_filters_products_from_expired_vendor_subscriptions(self):
        category = ProductCategory.objects.create(name="General")

        pkg = SubscriptionPackage.objects.create(
            package_name="Pro",
            package_description="Pro package",
            package_price="10.00",
            can_create_product=True,
            can_create_service=True,
        )

        # Expired vendor
        expired_user = User.objects.create_user(
            email="expired@example.com",
            phone="233000000001",
            name="Expired Vendor",
            password="Password123!",
            user_type=UserType.VENDOR.value,
            phone_verified=True,
            email_verified=True,
        )
        expired_vendor = Vendor.objects.create(
            user=expired_user,
            vendor_name="Expired Shop",
            vendor_phone="233500000001",
            vendor_email="expired-vendor@example.com",
            vendor_address="Accra",
        )
        Subscription.objects.create(
            vendor=expired_vendor,
            package=pkg,
            start_date=timezone.localdate() - timedelta(days=60),
            end_date=timezone.localdate() - timedelta(days=1),
        )
        expired_product = Product.objects.create(
            name="Expired Product",
            description="Should be filtered out",
            price="5.00",
            category=category,
            is_published=True,
            vendor=expired_vendor,
        )

        # Active vendor
        active_user = User.objects.create_user(
            email="active@example.com",
            phone="233000000002",
            name="Active Vendor",
            password="Password123!",
            user_type=UserType.VENDOR.value,
            phone_verified=True,
            email_verified=True,
        )
        active_vendor = Vendor.objects.create(
            user=active_user,
            vendor_name="Active Shop",
            vendor_phone="233500000002",
            vendor_email="active-vendor@example.com",
            vendor_address="Accra",
        )
        Subscription.objects.create(
            vendor=active_vendor,
            package=pkg,
            start_date=timezone.localdate() - timedelta(days=1),
            end_date=timezone.localdate() + timedelta(days=30),
        )
        active_product = Product.objects.create(
            name="Active Product",
            description="Should be visible",
            price="6.00",
            category=category,
            is_published=True,
            vendor=active_vendor,
        )

        # Platform-owned product (vendor is null) should always be included.
        platform_product = Product.objects.create(
            name="Platform Product",
            description="Should be visible",
            price="7.00",
            category=category,
            is_published=True,
            vendor=None,
        )

        url = reverse("apis:homepage")
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()

        # Collect all product ids returned across homepage sections.
        returned_ids = set()
        for key in ("products", "best_selling_products", "new_arrivals"):
            for p in data.get(key, []) or []:
                returned_ids.add(p.get("id"))

        self.assertIn(active_product.id, returned_ids)
        self.assertIn(platform_product.id, returned_ids)
        self.assertNotIn(expired_product.id, returned_ids)
