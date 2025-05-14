from django.db.models import Q
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import Subscription, Vendor
from apis.models import Order, Payment, ServiceBooking
from apis.serializers import PaymentSerializer
from bscore.utils.const import PaymentType, UserType
from bscore.utils.permissions import allow_domains
from bscore.utils.services import (can_cashout, execute_momo_transaction,
                                   get_transaction_status)


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
            vendor = Vendor.objects.filter(
                vendor_id=order.vendor_id).first()
        elif booking:
            booking = ServiceBooking.objects.filter(id=booking).first()
            if booking is None:
                return Response({
                    "message": "Booking not found",
                }, status=status.HTTP_400_BAD_REQUEST)
            vendor = booking.service.vendor
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
            vendor = Vendor.objects.filter(
                Q(vendor_name__icontains='Birthnon Account') | 
                Q(vendor_name__icontains='Birthnon Services'), 
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
            subscription.start_date = response.get('transaction').get('created_at')
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

    @allow_domains(['localhost:8000'],)
    def get(self, request, *args, **kwargs):
        '''Handle payment callback'''
        return Response({
            "message": "Callback received",
        }, status=status.HTTP_200_OK)
    
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