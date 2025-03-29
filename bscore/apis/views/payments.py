from rest_framework import status, permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from apis.models import Order, Payment, Product, ProductCategory
from apis.serializers import OrderSerializer, PaymentSerializer, ProductCategorySerializer, ProductSerializer
from bscore.utils.const import UserType
from bscore.utils.permissions import IsSuperuser, IsAdminOnly, IsCustomerOnly, IsEliteVendorOnly


class PaymentAPIView(APIView):
    '''API Endpoints for Payments (Read-only)'''
    permission_classes = (permissions.IsAuthenticated,)

    def get(self, request, *args, **kwargs):
        payments = Payment.objects.all().order_by('-created_at')
        serializer = PaymentSerializer(payments, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)