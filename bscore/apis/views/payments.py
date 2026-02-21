import hashlib
import hmac
import json

from django.conf import settings
from django.db.models import Q
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from drf_spectacular.utils import OpenApiExample, OpenApiResponse, extend_schema

import datetime
from accounts.models import Subscription, Vendor
from apis.models import Order, Payment, ServiceBooking
from apis.serializers import PaymentSerializer
from bscore.utils.const import PaymentType, UserType
from bscore.utils.services import (
    can_cashout,
    execute_momo_transaction,
    get_transaction_status,
    initiate_paystack_payment,
    finalize_paystack_payment,
)


class PaymentAPIView(APIView):
    '''API Endpoints for Payments (Read-only)'''
    permission_classes = (permissions.IsAuthenticated,)

    def get(self, request, *args, **kwargs):
        user = request.user
        if user.is_superuser or user.is_staff or user.user_type == UserType.ADMIN.value:
            payments = Payment.objects.all().order_by('-created_at')
        elif user.user_type == UserType.VENDOR.value:
            vendor = user.get_vendor()
            payments = Payment.objects.filter(vendor=vendor).order_by('-created_at')
        elif user.user_type == UserType.CUSTOMER.value:
            payments = Payment.objects.filter(user=user).order_by('-created_at')
        serializer = PaymentSerializer(payments, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
    

class VendorCashoutAPI(APIView):
    '''cashout from vendor wallet'''

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):
        '''Cashout from vendor wallet'''
        user = request.user
        amount = request.data.get('amount', None)
        if not amount:
            return Response({
                "message": "Amount is required",
            }, status=status.HTTP_400_BAD_REQUEST)
        if can_cashout(request, amount):
            vendor = Vendor.objects.filter(user=user).first()
            try:
                response = execute_momo_transaction(
                    request=request, type=PaymentType.CREDIT.value, 
                    vendor=vendor, withdrawal=True
                    )
            except Exception as e:
                return Response({
                    "message": str(e),
                }, status=status.HTTP_400_BAD_REQUEST)
            return Response(
                {
                    "status": response.get('transaction_status'),
                    "transaction": response.get('transaction')
                },
                status=response.get('api_status')
            )
        return Response({
            "message": "Withdrawal cannot be processed at this time",
            "status": "failed",
        }, status=status.HTTP_400_BAD_REQUEST)


class MakePaymentAPI(APIView):
    '''API Endpoint to make payment using mobile money'''
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):
        '''Make payment using mobile money'''
        subscription = request.data.get('subscription', None)
        order = request.data.get('order', None)
        booking = request.data.get('booking', None)
        vendor = None
        subscription = Subscription.objects.filter(id=subscription).first() if subscription else None
        order = request.data.get('order', None) if order else None
        booking = request.data.get('booking', None) if booking else None
        print(f"subscription: {subscription}")
        print(f"Vendor: {vendor}")
        if subscription:
            vendor = Vendor.objects.filter(
                Q(vendor_name__icontains='Birthnon Account') | 
                Q(vendor_name__icontains='Birthnon Services'), 
                Q(user__is_superuser=True)
                ).first()
        elif order:
            order = Order.objects.filter(id=order).first()
            if order is None:
                return Response({
                    "message": "Order not found",
                }, status=status.HTTP_400_BAD_REQUEST)
            # Orders can contain items from multiple vendors; do not force a single vendor.
            vendor = None
        elif booking:
            booking = ServiceBooking.objects.filter(id=booking).first()
            if booking is None:
                return Response({
                    "message": "Booking not found",
                }, status=status.HTTP_400_BAD_REQUEST)
            vendor = booking.service.vendor
        if vendor is None and not order:
            return Response({
                "message": "Vendor not found",
            }, status=status.HTTP_400_BAD_REQUEST)
        try:
            response = execute_momo_transaction(
                request=request, 
                type=PaymentType.DEBIT.value, # debit the user and credit to the vendor
                vendor=vendor,
                subscription=subscription,
                order=order,
                booking=booking,
                withdrawal=False,
                )
        except Exception as e:
            print(f"Exception caught: {e}")
            return Response({
                "message": str(e),
            }, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            {
                "status": response.get('transaction_status'),
                "message": response.get('message'),
                "transaction": response.get('transaction')
            },
            status=response.get('api_status')
        )


class MakePaystackPaymentAPI(APIView):
    '''API Endpoint to initialize Paystack payment (web/mobile).'''
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):
        subscription = request.data.get('subscription', None)
        order = request.data.get('order', None)
        booking = request.data.get('booking', None)
        vendor = None
        subscription = Subscription.objects.filter(id=subscription).first() if subscription else None
        order = Order.objects.filter(id=order).first() if order else None
        booking = ServiceBooking.objects.filter(id=booking).first() if booking else None

        if subscription:
            vendor = Vendor.objects.filter(
                Q(vendor_name__icontains='Birthnon Account') |
                Q(vendor_name__icontains='Birthnon Services') |
                Q(vendor_name__icontains='Birthnon'),
                Q(user__is_superuser=True)
            ).first()
        elif order:
            if order is None:
                return Response({"message": "Order not found"}, status=status.HTTP_400_BAD_REQUEST)
            vendor = None
        elif booking:
            if booking is None:
                return Response({"message": "Booking not found"}, status=status.HTTP_400_BAD_REQUEST)
            vendor = booking.service.vendor

        if vendor is None and not order:
            return Response({"message": "Vendor not found"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            result = initiate_paystack_payment(
                request=request,
                vendor=vendor,
                subscription=subscription,
                order=order,
                booking=booking,
            )
        except Exception as e:
            return Response({"message": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(result, status=result.get('api_status', status.HTTP_200_OK))

        
class SubscriptionRenewalAPIView(APIView):
    '''API Endpoint for renewal of subscriptions'''
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):
        '''Make payment using mobile money'''
        subscription = request.data.get('subscription', None)
        vendor = None
        subscription = Subscription.objects.filter(id=subscription).first() if subscription else None
        print(f"subscription: {subscription}")
        print(f"Vendor: {vendor}")
        if subscription:
            # ensure only active subscriptions can be renewed
            if subscription.expired == False:
                return Response({
                    "message": "You cannot renew active subscription"
                }, status=status.HTTP_400_BAD_REQUEST)
            # get the default birthnon vendor profile
            vendor = Vendor.objects.filter(
                Q(vendor_name__icontains='Birthnon Account') | 
                Q(vendor_name__icontains='Birthnon Services') |
                Q(vendor_name__icontains='Birthnon'), 
                Q(user__is_superuser=True)
                ).first()
        else:
            return Response({
                "message": "Subscription not found",
            }, status=status.HTTP_400_BAD_REQUEST)
        if vendor is None:
            return Response({
                "message": "Vendor not found",
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            response = execute_momo_transaction(
                request=request, 
                type=PaymentType.DEBIT.value, # debit the user and credit to the vendor
                vendor=vendor,
                subscription=subscription,
                withdrawal=False,
                )
        except Exception as e:
            print(f"Exception caught: {e}")
            return Response({
                "message": str(e),
            }, status=status.HTTP_400_BAD_REQUEST)
        # check if payment is successful and update subscription
        print('response:', response)
        if response.get('transaction').get('status_code') == '000':
            # set the start and end date of the subscription
            print('response:', response)
            subscription.start_date = datetime.date.today()
            # add 30 days to the start date
            subscription.end_date = datetime.date.today() + datetime.timedelta(days=30)
            subscription.save()
        return Response(
            {
                "status": response.get('transaction_status'),
                "message": response.get('message'),
                "transaction": response.get('transaction')
            },
            status=response.get('api_status')
        )


class PaymentCallbackAPI(APIView):
    '''API Endpoint to handle payment callback'''
    permission_classes = [permissions.AllowAny]

    def get(self, request, *args, **kwargs):
        '''Handle payment callback from Paystack (redirect with reference).'''
        reference = request.query_params.get('reference') or request.query_params.get('payment_id')
        if not reference:
            return Response({"message": "reference is required"}, status=status.HTTP_400_BAD_REQUEST)
        result = finalize_paystack_payment(reference)
        return Response(result, status=result.get('api_status', status.HTTP_200_OK))


class PaystackWebhookAPI(APIView):
    """Webhook receiver for Paystack transaction updates.

    Paystack will POST events to this endpoint.
    We verify the request signature using PAYSTACK_SECRET_KEY and then reconcile our local Payment.
    """

    permission_classes = [permissions.AllowAny]

    def post(self, request, *args, **kwargs):
        signature = request.headers.get('x-paystack-signature') or request.META.get('HTTP_X_PAYSTACK_SIGNATURE')
        if not signature:
            return Response({"message": "Missing x-paystack-signature"}, status=status.HTTP_400_BAD_REQUEST)

        secret = getattr(settings, 'PAYSTACK_SECRET_KEY', None)
        if not secret:
            return Response({"message": "Paystack secret key not configured"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        raw_body = request.body or b''
        computed = hmac.new(
            key=str(secret).encode('utf-8'),
            msg=raw_body,
            digestmod=hashlib.sha512,
        ).hexdigest()

        if not hmac.compare_digest(computed, str(signature)):
            return Response({"message": "Invalid signature"}, status=status.HTTP_401_UNAUTHORIZED)

        try:
            payload = json.loads(raw_body.decode('utf-8') if raw_body else '{}')
        except Exception:
            return Response({"message": "Invalid JSON"}, status=status.HTTP_400_BAD_REQUEST)

        event = payload.get('event')
        data = payload.get('data') or {}
        reference = data.get('reference')

        # For transaction events without reference we can't reconcile.
        if not reference:
            return Response({"status": "ignored", "message": "Missing reference"}, status=status.HTTP_200_OK)

        # Only reconcile for known transaction-related events.
        # This keeps the webhook fast and avoids doing work for unrelated events.
        allowed_events = {
            'charge.success',
            'charge.failed',
            'transaction.success',
            'transaction.failed',
        }
        if event and event not in allowed_events:
            return Response({"status": "ignored", "event": event}, status=status.HTTP_200_OK)

        # Reconcile by verifying against Paystack API (safe + idempotent).
        result = finalize_paystack_payment(reference)
        api_status = int(result.get('api_status', status.HTTP_200_OK) or status.HTTP_200_OK)

        # Paystack will retry on non-2xx responses.
        # - For expected client-ish outcomes (e.g., unknown reference), return 200 to avoid endless retries.
        # - For real server-side failures, return 500 so Paystack retries later.
        if api_status >= 500:
            return Response({"status": "error", "event": event, "result": result}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response({"status": "ok", "event": event, "result": result}, status=status.HTTP_200_OK)
    
class PaymentStatusCheckAPI(APIView):
    '''API Endpoint to check payment status'''
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, *args, **kwargs):
        '''Check payment status'''
        payment_id = request.query_params.get('payment_id', None)
        if not payment_id:
            return Response({
                "message": "Payment ID is required",
            }, status=status.HTTP_400_BAD_REQUEST)
        payment = Payment.objects.filter(payment_id=payment_id).first()
        if not payment:
            return Response({
                "message": "Payment not found",
            }, status=status.HTTP_404_NOT_FOUND)
        # check if payment is successful
        response = get_transaction_status(payment.payment_id)
        payment.status_code = response.get('status_code')
        payment.status = response.get('message')
        payment.save()
        serializer = PaymentSerializer(payment)
        return Response(serializer.data, status=status.HTTP_200_OK)


class PaystackVerifyAPI(APIView):
    '''API Endpoint to verify Paystack payment reference and update records.'''
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        summary='Paystack status check (verify by reference)',
        description=(
            'Verifies a Paystack transaction by `reference` and updates the local Payment record. '
            'Safe to call multiple times (idempotent): it will not create duplicate payouts or double-credit wallets.'
        ),
        responses={
            200: OpenApiResponse(description='Verification result'),
            400: OpenApiResponse(description='Invalid reference / verification failed'),
            401: OpenApiResponse(description='Authentication required'),
            404: OpenApiResponse(description='Payment not found'),
        },
        examples=[
            OpenApiExample(
                'Verify Request',
                value={"reference": "psk_ref_123"},
                request_only=True,
                description='Send as query param: ?reference=psk_ref_123',
            ),
            OpenApiExample(
                'Verify Success Response',
                value={
                    "status": "SUCCESS",
                    "transaction": {
                        "payment_id": "psk_ref_123",
                        "payment_method": "PAYSTACK",
                        "status": "SUCCESS",
                        "status_code": "000",
                        "amount": "50.00"
                    },
                    "api_status": 200,
                },
                response_only=True,
            ),
        ],
    )
    def get(self, request, *args, **kwargs):
        reference = request.query_params.get('reference') or request.query_params.get('payment_id')
        if not reference:
            return Response({"message": "reference is required"}, status=status.HTTP_400_BAD_REQUEST)
        result = finalize_paystack_payment(reference)
        return Response(result, status=result.get('api_status', status.HTTP_200_OK))