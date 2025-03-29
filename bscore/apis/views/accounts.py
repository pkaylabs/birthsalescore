from rest_framework import status, permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import Subscription, SubscriptionPackage, Vendor, Wallet
from apis.models import Product
from apis.serializers import ProductSerializer, SubscriptionPackageSerializer, SubscriptionSerializer, VendorSerializer, WalletSerializer
from bscore.utils.const import UserType
from bscore.utils.permissions import IsSuperuser, IsAdminOnly, IsCustomerOnly, IsEliteVendorOnly


class VendorAPIView(APIView):
    '''API Endpoints for Vendors'''

    permission_classes = (IsSuperuser | IsAdminOnly,)

    def get(self, request, *args, **kwargs):
        '''Retrieve all vendors (Only admins can access)'''
        vendors = Vendor.objects.all().order_by('-created_at')
        serializer = VendorSerializer(vendors, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request, *args, **kwargs):
        '''Register a new vendor (Only admins can create vendors)'''
        serializer = VendorSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response({"message": "Vendor registered successfully", "vendor": serializer.data}, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, *args, **kwargs):
        '''Delete a vendor (Only superusers can delete vendors)'''
        user = request.user
        vendor_id = request.data.get('vendor_id')
        vendor = Vendor.objects.filter(id=vendor_id).first()

        if not vendor:
            return Response({"message": "Vendor not found"}, status=status.HTTP_404_NOT_FOUND)
        
        vendor.delete()
        return Response({"message": "Vendor deleted successfully"}, status=status.HTTP_200_OK)
    
class SubscriptionAPIView(APIView):
    '''API Endpoints for Subscriptions'''
    permission_classes = (permissions.IsAuthenticated,)

    def get(self, request, *args, **kwargs):
        subscriptions = Subscription.objects.all().order_by('-created_at')
        serializer = SubscriptionSerializer(subscriptions, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

class SubscriptionPackageAPIView(APIView):
    '''API Endpoints for Subscription Packages'''
    permission_classes = (permissions.IsAuthenticated,)

    def get(self, request, *args, **kwargs):
        packages = SubscriptionPackage.objects.all()
        serializer = SubscriptionPackageSerializer(packages, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
class WalletAPIView(APIView):
    '''API Endpoints for Wallets'''
    permission_classes = (permissions.IsAuthenticated,)

    def get(self, request, *args, **kwargs):
        wallets = Wallet.objects.all().order_by('-created_at')
        serializer = WalletSerializer(wallets, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
