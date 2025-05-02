from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apis.models import Payment
from apis.serializers import PaymentSerializer


class PaymentAPIView(APIView):
    '''API Endpoints for Payments (Read-only)'''
    permission_classes = (permissions.IsAuthenticated,)

    def get(self, request, *args, **kwargs):
        payments = Payment.objects.all().order_by('-created_at')
        serializer = PaymentSerializer(payments, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)