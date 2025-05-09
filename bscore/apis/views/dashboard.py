from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import User, Vendor, Wallet
from apis.models import Order, Payment, Product
from apis.serializers import PaymentSerializer
from bscore.utils.const import UserType
from bscore.utils.permissions import (IsAdminOnly, IsEliteVendorOnly,
                                      IsSuperuserOnly)


class DashboardAPIView(APIView):
    '''Endpoint to get basic stats for the dashboard'''

    permission_classes = (IsSuperuserOnly | IsAdminOnly | IsEliteVendorOnly, )

    def get(self, request, *args, **kwawrgs):
        user = request.user
        data = None
        now = timezone.now()
        start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_day = start_of_day + timezone.timedelta(days=1)

        if user.user_type == UserType.VENDOR.value:
            vendor = Vendor.objects.filter(user=user).first()
            wallet = Wallet.objects.filter(vendor=vendor).first()
            products = Product.objects.filter(vendor=vendor).count()
            # technical dept
            orders = len([ord for ord in Order.objects.all() if ord.vendor_id == vendor.vendor_id])
            sales_today = sum([p.amount for p in Payment.objects.filter(
                vendor=vendor,
                created_at__gte=start_of_day,
                created_at__lt=end_of_day
            )])
            balance = wallet.balance
            users = 1
            payments = Payment.objects.filter(vendor=vendor).order_by('-created_at')[:5]
        else:
            users = User.objects.count()
            products = Product.objects.count()
            orders = Order.objects.count()
            balance = sum([w.balance for w in Wallet.objects.all()])
            payments = Payment.objects.all().order_by('-created_at')[:5]
            sales_today = sum([p.amount for p in Payment.objects.filter(
                created_at__gte=start_of_day,
                created_at__lt=end_of_day
            )])

        data = {
                "products": products,
                "balance": balance,
                "users": users,
                "orders": orders,
                "latest_transactions": PaymentSerializer(payments, many=True).data,
                "sales_today": sales_today
            }
        
        return Response(data, status=status.HTTP_200_OK)



# users -- done
# products -- done
# orders -- done
# balance -- done
# sales made today -- done
# last 6 months revenue
# latest transactions (top 5) -- done