from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework.test import APIClient

from accounts.models import User
from apis.models import Payment, Refund
from bscore.utils.const import PaymentMethod, PaymentStatus, PaymentStatusCode, PaymentType, UserType


@override_settings(PAYSTACK_SECRET_KEY="sk_test_dummy")
class RefundUserEndpointTests(TestCase):
    def setUp(self):
        self.client = APIClient()

        self.admin = User.objects.create_superuser(
            email="admin@example.com",
            phone="233000000010",
            name="Admin",
            password="Password123!",
            user_type=UserType.ADMIN.value,
        )

        self.customer = User.objects.create_user(
            email="customer@example.com",
            phone="233000000011",
            name="Customer",
            password="Password123!",
            user_type=UserType.CUSTOMER.value,
        )

        self.payment = Payment.objects.create(
            payment_id="pay_123",
            order=None,
            booking=None,
            subscription=None,
            user=self.customer,
            vendor=None,
            amount=Decimal("10.00"),
            reason="Test payment",
            payment_method=PaymentMethod.PAYSTACK.value,
            payment_type=PaymentType.DEBIT.value,
            status=PaymentStatus.SUCCESS.value,
            status_code=PaymentStatusCode.SUCCESS.value,
        )

    def test_non_admin_cannot_refund(self):
        self.client.force_authenticate(user=self.customer)
        url = reverse("apis:refund_user")
        resp = self.client.post(url, data={"payment_id": self.payment.payment_id}, format="json")
        self.assertEqual(resp.status_code, 403)

    @patch("apis.views.payments.paystack_create_transfer_recipient")
    @patch("apis.views.payments.paystack_initiate_transfer")
    def test_admin_refund_is_idempotent(self, mock_initiate, mock_recipient):
        mock_recipient.return_value = {
            "status": True,
            "data": {"recipient_code": "RCP_TEST"},
        }
        mock_initiate.return_value = {
            "status": True,
            "data": {"status": "success", "transfer_code": "TRF_TEST"},
        }

        self.client.force_authenticate(user=self.admin)
        url = reverse("apis:refund_user")
        payload = {
            "payment_id": self.payment.payment_id,
            "phone": "233500000000",
            "provider_code": "MTN",
            "recipient_type": "mobile_money",
            "currency": "GHS",
        }

        r1 = self.client.post(url, data=payload, format="json")
        self.assertEqual(r1.status_code, 200)

        # Payment should be marked refunded on success.
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, PaymentStatus.REFUNDED.value)
        self.assertIsNotNone(self.payment.refunded_date)

        # Refund record should exist.
        self.assertTrue(Refund.objects.filter(payment=self.payment).exists())

        # Second call should not initiate another transfer.
        r2 = self.client.post(url, data=payload, format="json")
        self.assertEqual(r2.status_code, 200)
        self.assertEqual(mock_recipient.call_count, 1)
        self.assertEqual(mock_initiate.call_count, 1)

    def test_non_admin_cannot_list_refunds(self):
        self.client.force_authenticate(user=self.customer)
        url = reverse("apis:refund_user")
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 403)

    def test_admin_can_list_refunds(self):
        # Create a refund record.
        self.payment.status = PaymentStatus.REFUNDED.value
        self.payment.save()
        Refund.objects.create(
            payment=self.payment,
            refunded_by=self.admin,
            recipient_type="mobile_money",
            phone="233500000000",
            provider_code="MTN",
            currency="GHS",
            name="Customer",
            amount=self.payment.amount,
            reason="Refund",
            recipient_code="RCP_TEST",
            transfer_code="TRF_TEST",
            status=PaymentStatus.SUCCESS.value,
            status_code=PaymentStatusCode.SUCCESS.value,
        )

        self.client.force_authenticate(user=self.admin)
        url = reverse("apis:refund_user")
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertIsInstance(resp.data, list)
        self.assertGreaterEqual(len(resp.data), 1)
        self.assertIn("payment_id", resp.data[0])
