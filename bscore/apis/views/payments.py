from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import Subscription, Vendor
from apis.models import Payment
from apis.serializers import PaymentSerializer
from bscore.utils.const import PaymentType, UserType
from bscore.utils.services import can_cashout, execute_momo_transaction


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
            vendor = user.get_vendor()
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
        vendor = None
        subscription = Subscription.objects.filter(id=subscription).first() if subscription else None
        if subscription:
            vendor = Vendor.objects.filter(vendor_name__icontains='Birthon Account').first()
            if not vendor:
                return Response({
                    "message": "Vendor not found",
                }, status=status.HTTP_400_BAD_REQUEST)
        try:
            response = execute_momo_transaction(
                request=request, 
                type=PaymentType.DEBIT.value,
                vendor=vendor,
                withdrawal=False,
                )
        except Exception as e:
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

