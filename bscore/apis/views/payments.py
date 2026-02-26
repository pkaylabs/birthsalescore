import hashlib
import hmac
import json

from django.conf import settings
from django.utils import timezone
from django.db.models import F, Q
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from drf_spectacular.utils import OpenApiExample, OpenApiResponse, extend_schema

import datetime
from accounts.models import Subscription, Vendor
from apis.models import Order, Payment, PaystackWebhookEvent, ServiceBooking
from apis.serializers import PaymentSerializer
from bscore.utils.const import PaymentStatus, PaymentStatusCode, PaymentType, UserType
from bscore.utils.services import (
    can_cashout,
    execute_momo_transaction,
    get_transaction_status,
    apply_payment_success_effects,
    initiate_paystack_payment,
    finalize_paystack_payment,
    initiate_paystack_cashout,
    finalize_paystack_cashout,
    verify_paystack_cashout,
    paystack_list_banks,
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


class PaystackCashoutInitiateAPI(APIView):
    """Initiate a vendor cashout via Paystack Transfer.

    This does NOT replace the existing PayHub-based `/cashout/` endpoint.
    It creates a PAYSTACK/CREDIT Payment and debits the vendor wallet only after transfer success.
    """

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):
        user = request.user
        if not (
            user.is_superuser
            or user.is_staff
            or user.user_type == UserType.ADMIN.value
            or user.user_type == UserType.VENDOR.value
        ):
            return Response({"message": "Not authorized"}, status=status.HTTP_403_FORBIDDEN)

        amount = request.data.get('amount')
        if not amount:
            return Response({"message": "Amount is required"}, status=status.HTTP_400_BAD_REQUEST)

        # Validate amount early to avoid Decimal conversion errors inside can_cashout.
        try:
            import decimal
            decimal.Decimal(str(amount))
        except Exception:
            return Response({"message": "Invalid amount"}, status=status.HTTP_400_BAD_REQUEST)

        if not can_cashout(request, amount):
            return Response({
                "message": "Withdrawal cannot be processed at this time",
                "status": "failed",
            }, status=status.HTTP_400_BAD_REQUEST)

        vendor = Vendor.objects.filter(user=user).first()
        if not vendor:
            return Response({"message": "Vendor not found"}, status=status.HTTP_400_BAD_REQUEST)

        recipient_type = request.data.get('recipient_type')
        name = request.data.get('name')
        account_number = request.data.get('account_number')
        bank_code = request.data.get('bank_code')
        currency = request.data.get('currency') or 'GHS'
        reason = request.data.get('reason')

        missing = [
            key for key, val in {
                'recipient_type': recipient_type,
                'name': name,
                'account_number': account_number,
                'bank_code': bank_code,
            }.items() if not val
        ]
        if missing:
            return Response({
                "message": f"Missing fields: {', '.join(missing)}",
            }, status=status.HTTP_400_BAD_REQUEST)

        try:
            result = initiate_paystack_cashout(
                request=request,
                vendor=vendor,
                recipient_type=str(recipient_type),
                name=str(name),
                account_number=str(account_number),
                bank_code=str(bank_code),
                currency=str(currency),
                reason=str(reason) if reason else None,
            )
        except Exception as e:
            return Response({"message": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(result, status=result.get('api_status', status.HTTP_200_OK))


class PaystackCashoutFinalizeAPI(APIView):
    """Finalize a Paystack transfer that requires OTP."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):
        user = request.user
        if not (
            user.is_superuser
            or user.is_staff
            or user.user_type == UserType.ADMIN.value
            or user.user_type == UserType.VENDOR.value
        ):
            return Response({"message": "Not authorized"}, status=status.HTTP_403_FORBIDDEN)

        reference = request.data.get('reference') or request.data.get('payment_reference')
        transfer_code = request.data.get('transfer_code')
        otp = request.data.get('otp')

        if not reference or not transfer_code or not otp:
            return Response({
                "message": "reference, transfer_code and otp are required",
            }, status=status.HTTP_400_BAD_REQUEST)

        # Ownership check: vendors can only finalize their own cashouts.
        vendor = Vendor.objects.filter(user=user).first()
        if user.user_type == UserType.VENDOR.value and vendor:
            payment = Payment.objects.filter(payment_id=reference).first()
            if payment and payment.vendor_id != vendor.id:
                return Response({"message": "Not authorized"}, status=status.HTTP_403_FORBIDDEN)

        try:
            result = finalize_paystack_cashout(
                payment_reference=str(reference),
                transfer_code=str(transfer_code),
                otp=str(otp),
            )
        except Exception as e:
            return Response({"message": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(result, status=result.get('api_status', status.HTTP_200_OK))


class PaystackCashoutVerifyAPI(APIView):
    """Verify a Paystack transfer by reference and update local Payment."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, *args, **kwargs):
        user = request.user
        if not (
            user.is_superuser
            or user.is_staff
            or user.user_type == UserType.ADMIN.value
            or user.user_type == UserType.VENDOR.value
        ):
            return Response({"message": "Not authorized"}, status=status.HTTP_403_FORBIDDEN)

        reference = request.query_params.get('reference') or request.query_params.get('payment_reference')
        if not reference:
            return Response({"message": "reference is required"}, status=status.HTTP_400_BAD_REQUEST)

        # Ownership check for vendors.
        vendor = Vendor.objects.filter(user=user).first()
        if user.user_type == UserType.VENDOR.value and vendor:
            payment = Payment.objects.filter(payment_id=reference).first()
            if payment and payment.vendor_id != vendor.id:
                return Response({"message": "Not authorized"}, status=status.HTTP_403_FORBIDDEN)

        try:
            result = verify_paystack_cashout(payment_reference=str(reference))
        except Exception as e:
            return Response({"message": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(result, status=result.get('api_status', status.HTTP_200_OK))


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

        # Subscription dates are updated via centralized idempotent post-payment effects
        # (triggered within execute_momo_transaction / status checks). Do not mutate here.
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

        # If we don't have a local Payment yet, record the webhook and ACK (avoid Paystack retry storms).
        if not Payment.objects.filter(payment_id=reference).exists():
            try:
                PaystackWebhookEvent.objects.create(
                    event=event,
                    reference=str(reference),
                    signature=str(signature),
                    payload=payload,
                    processed=False,
                    attempts=0,
                )
            except Exception:
                # If we can't persist the event, ask Paystack to retry.
                return Response({"status": "error", "message": "Could not record webhook"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            return Response({"status": "queued", "event": event, "reference": reference}, status=status.HTTP_200_OK)

        # Reconcile by verifying against Paystack API (safe + idempotent).
        result = finalize_paystack_payment(reference)
        api_status = int(result.get('api_status', status.HTTP_200_OK) or status.HTTP_200_OK)

        # Paystack will retry on non-2xx responses.
        # - For expected client-ish outcomes (e.g., unknown reference), return 200 to avoid endless retries.
        # - For real server-side failures, return 500 so Paystack retries later.
        if api_status >= 500:
            return Response({"status": "error", "event": event, "result": result}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # Mark any previously queued events for this reference as processed once the payment is terminal.
        # Terminal states: SUCCESS / FAILED.
        terminal_statuses = {PaymentStatus.SUCCESS.value, PaymentStatus.FAILED.value}
        if result.get('status') in terminal_statuses:
            try:
                last_error = None
                if result.get('status') == PaymentStatus.FAILED.value:
                    last_error = 'Terminal FAILED reconciliation'
                PaystackWebhookEvent.objects.filter(reference=str(reference), processed=False).update(
                    processed=True,
                    processed_at=timezone.now(),
                    attempts=F('attempts') + 1,
                    last_error=last_error,
                )
            except Exception:
                pass

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
        response = get_transaction_status(payment.payment_id)
        provider_code = response.get('status_code')

        already_success = (
            payment.status == PaymentStatus.SUCCESS.value
            and payment.status_code == PaymentStatusCode.SUCCESS.value
        )

        # Normalize provider codes into our PaymentStatus/PaymentStatusCode.
        if provider_code == PaymentStatusCode.SUCCESS.value:
            payment.status = PaymentStatus.SUCCESS.value
            payment.status_code = PaymentStatusCode.SUCCESS.value
        elif provider_code == PaymentStatusCode.FAILED.value:
            # Never downgrade a successful payment.
            if not already_success:
                payment.status = PaymentStatus.FAILED.value
                payment.status_code = PaymentStatusCode.FAILED.value
        else:
            # Treat unknown codes as pending.
            if not already_success:
                payment.status = PaymentStatus.PENDING.value
                payment.status_code = PaymentStatusCode.PENDING.value

        payment.save()

        # If the payment is now successful, apply post-success effects safely.
        if payment.status == PaymentStatus.SUCCESS.value and payment.status_code == PaymentStatusCode.SUCCESS.value:
            try:
                payment = apply_payment_success_effects(payment)
            except Exception:
                # Don't fail the status check response; consider logging in future.
                pass

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


class PaystackBanksAPIView(APIView):
    """Fetch Paystack bank and mobile money provider codes.

    This proxies Paystack's `GET /bank`.
    Pass-through query params (optional):
    - currency (e.g., GHS)
    - type (e.g., mobile_money)
    - country (e.g., ghana)
    - perPage, page
    """

    permission_classes = (permissions.AllowAny,)

    @extend_schema(
        summary='Paystack bank/provider codes (list banks/mobile money providers)',
        description=(
            'Returns Paystack bank list; for mobile money providers, pass `type=mobile_money`. '
            'Example: `/paystack/banks/?currency=GHS&type=mobile_money&country=ghana`.'
        ),
        responses={
            200: OpenApiResponse(description='Paystack bank/provider list'),
            500: OpenApiResponse(description='Paystack secret key not configured'),
        },
        examples=[
            OpenApiExample(
                'Mobile Money Providers (GHS)',
                value={
                    'status': True,
                    'message': 'Banks retrieved',
                    'data': [
                        {
                            'name': 'MTN MoMo',
                            'slug': 'mtn',
                            'code': 'MTN',
                            'longcode': '',
                            'gateway': '',
                            'pay_with_bank': False,
                            'active': True,
                            'currency': 'GHS',
                            'type': 'mobile_money',
                        }
                    ]
                },
                response_only=True,
            )
        ],
    )
    def get(self, request, *args, **kwargs):
        secret = getattr(settings, 'PAYSTACK_SECRET_KEY', None)
        if not secret:
            return Response(
                {"message": "Paystack secret key not configured"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        allowed = {'currency', 'type', 'country', 'perPage', 'page'}
        params = {
            k: v for k, v in request.query_params.items()
            if k in allowed and v not in (None, '')
        }

        try:
            result = paystack_list_banks(params=params or None)
        except Exception as e:
            return Response(
                {"message": str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Paystack returns JSON with `status`, `message`, `data`.
        # Surface provider errors as 400 to the client.
        if not result.get('status'):
            return Response(result, status=status.HTTP_400_BAD_REQUEST)

        return Response(result, status=status.HTTP_200_OK)