from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from accounts.models import Subscription, SubscriptionPackage, User, Vendor
from apis.models import Payment
from bscore.utils.const import PaymentStatus, PaymentStatusCode, UserType
from bscore.utils.services import apply_payment_success_effects


class SubscriptionLifecycleTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="vendor@example.com",
            phone="233000000010",
            name="Vendor User",
            password="Password123!",
            user_type=UserType.VENDOR.value,
            phone_verified=True,
            email_verified=True,
        )
        self.vendor = Vendor.objects.create(
            user=self.user,
            vendor_name="Vendor Shop",
            vendor_phone="233500000010",
            vendor_email="vendor-shop@example.com",
            vendor_address="Accra",
        )
        self.package = SubscriptionPackage.objects.create(
            package_name="Basic",
            package_description="Basic package",
            package_price="10.00",
            can_create_product=True,
            can_create_service=False,
        )

    def create_successful_payment(self, subscription):
        return Payment.objects.create(
            subscription=subscription,
            user=self.user,
            amount=self.package.package_price,
            status=PaymentStatus.SUCCESS.value,
            status_code=PaymentStatusCode.SUCCESS.value,
        )

    def test_new_subscription_is_not_active_before_successful_payment(self):
        subscription = Subscription.objects.create(
            vendor=self.vendor,
            package=self.package,
        )

        self.assertIsNone(subscription.end_date)
        self.assertTrue(subscription.expired)
        self.assertFalse(self.vendor.has_active_subscription())

    def test_first_successful_payment_activates_for_one_month(self):
        today = timezone.localdate()
        subscription = Subscription.objects.create(
            vendor=self.vendor,
            package=self.package,
            start_date=today,
            end_date=today + timedelta(days=30),
        )
        payment = self.create_successful_payment(subscription)

        apply_payment_success_effects(payment)
        subscription.refresh_from_db()
        payment.refresh_from_db()

        self.assertEqual(subscription.start_date, today)
        self.assertEqual(subscription.end_date, today + timedelta(days=30))
        self.assertTrue(payment.subscription_effects_applied)
        self.assertFalse(subscription.expired)

    def test_renewal_extends_existing_paid_subscription_by_one_month(self):
        today = timezone.localdate()
        subscription = Subscription.objects.create(
            vendor=self.vendor,
            package=self.package,
            start_date=today,
            end_date=today + timedelta(days=30),
        )
        self.create_successful_payment(subscription)
        renewal_payment = self.create_successful_payment(subscription)

        apply_payment_success_effects(renewal_payment)
        subscription.refresh_from_db()

        self.assertEqual(subscription.start_date, today)
        self.assertEqual(subscription.end_date, today + timedelta(days=60))
