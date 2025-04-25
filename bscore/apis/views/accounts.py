from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import (Subscription, SubscriptionPackage, User, Vendor,
                             Wallet)
from apis.serializers import (SubscriptionPackageSerializer,
                              SubscriptionSerializer, UserSerializer,
                              VendorSerializer, WalletSerializer)
from bscore.utils.const import UserType
from bscore.utils.permissions import (IsAdminOnly, IsSuperuserOnly)


class UsersAPIView(APIView):
    '''API Endpoints for managing users'''

    permission_classes = (IsSuperuserOnly | IsAdminOnly,)

    def get(self, request, *args, **kwargs):
        '''Retrieve all users (Only admins can access)'''
        users = User.objects.all().order_by('-created_at')
        serializer = UserSerializer(users, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request, *args, **kwargs):
        '''Register a new user (Only admins can create users)'''
        serializer = UserSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response({"message": "User Created Successfully", "user": serializer.data}, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, *args, **kwargs):
        '''Delete a vendor (Only superusers can delete vendors)'''
        # user = request.user
        user_id = request.data.get('user_id')
        user = User.objects.filter(id=user_id, deleted=False).first()

        if not user:
            return Response({"message": "User not found"}, status=status.HTTP_404_NOT_FOUND)
        
        if user.id == request.user.id:
            return Response({"message": "You can't delete yourself"}, status=status.HTTP_404_NOT_FOUND)
        
        if user.is_superuser:
            return Response({"message": "You can't delete a Superuser"}, status=status.HTTP_404_NOT_FOUND)
        
        user.deleted = True
        user.save()
        return Response({"message": "User Account Deleted"}, status=status.HTTP_200_OK)


class VendorsAPIView(APIView):
    '''API Endpoints for Vendors'''

    permission_classes = (IsSuperuserOnly | IsAdminOnly,)

    def get(self, request, *args, **kwargs):
        '''Retrieve all vendors (Only admins can access)'''
        vendors = Vendor.objects.all().order_by('-created_at')
        serializer = VendorSerializer(vendors, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request, *args, **kwargs):
        '''Register a new vendor (Only admins can create vendors)'''
        serializer = VendorSerializer(data=request.data)
        if serializer.is_valid():
            user_id = request.data.get('user')
            user = User.objects.filter(id=user_id).first()
            if not user:
                return Response({"message": "User not found"}, status=status.HTTP_404_NOT_FOUND)
            user.user_type = UserType.VENDOR.value
            serializer.save()
            user.save()
            return Response({"message": "Vendor registered successfully", "vendor": serializer.data}, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    

class VendorProfileAPIView(APIView):
    '''Vendors use this to get and setup their vendor profile'''

    permission_classes = (permissions.IsAuthenticated,)

    def get(self, request, *args, **kwargs):
        '''get's the vendor profile'''
        user = request.user
        vendor = Vendor.objects.filter(user=user).first()
        context = {
            "user": UserSerializer(user).data,
            "vendor": VendorSerializer(vendor).data
        }
        return Response(context, status=status.HTTP_200_OK)
    
    def post(self, request, *args, **kwargs):
        '''Register a new vendor profile - for vendors'''
        serializer = VendorSerializer(data=request.data)
        if serializer.is_valid():
            user = request.user
            if not user:
                return Response({"message": "User not found"}, status=status.HTTP_404_NOT_FOUND)
            vendor = Vendor.objects.filter(user=user).first()
            if vendor:
                # if vendor profile already exists, update it with the new data
                serializer = VendorSerializer(vendor, data=request.data, partial=True)
                if serializer.is_valid():
                    serializer.save()
                    return Response({"message": "Vendor profile updated successfully", "vendor": serializer.data}, status=status.HTTP_200_OK)
                return Response({"error": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
            user.user_type = UserType.VENDOR.value
            serializer.save(user=user)
            user.save()
            return Response({"message": "Vendor registered successfully", "vendor": serializer.data}, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class SubscriptionAPIView(APIView):
    '''API Endpoints for Subscriptions'''
    permission_classes = (permissions.IsAuthenticated,)
    serializer_class = SubscriptionSerializer

    def get(self, request, *args, **kwargs):
        '''GET all subscriptions'''
        user = request.user
        if user.is_superuser or user.is_staff or user.user_type == UserType.ADMIN.value:
            subscriptions = Subscription.objects.all().order_by('-created_at')
        else:
            vendor = Vendor.objects.filter(user=user).first()
            subscriptions = Subscription.objects.filter(
                vendor=vendor
            ).order_by('-created_at')
        serializer = self.serializer_class(subscriptions, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    def post(self, request, *args, **kwars):
        '''For vendors to subscribe to a subscription package'''
        user = request.user
        vendor = Vendor.objects.filter(user=user).first()
        if vendor is not None:
            request.data['vendor'] = vendor.id
        else:
            return Response( {"message": "There is no vendor profile to your account"},status=status.HTTP_400_BAD_REQUEST)
        serializer = self.serializer_class(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)



class SubscriptionPackageAPIView(APIView):
    '''API Endpoints for Subscription Packages'''
    permission_classes = (permissions.IsAuthenticated,)
    serializer_class = SubscriptionPackageSerializer

    def get(self, request, *args, **kwargs):
        packages = SubscriptionPackage.objects.all()
        serializer = self.serializer_class(packages, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    def post(self, request, *args, **kwargs):
        user = request.user
        if not (user.is_superuser or user.is_staff or user.user_type == UserType.ADMIN.value):
            # only admin users can create subscription packages
            return Response({"message": "You are not authorised to create packages"}, status=status.HTTP_403_FORBIDDEN)
        serializer = self.serializer_class(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    def delete(self, request, *args, **kwargs):
        user = request.user
        if not (user.is_superuser or user.is_staff or user.user_type == UserType.ADMIN.value):
            # only admin users can create subscription packages
            return Response({"message": "You are not authorised to delete packages"}, status=status.HTTP_403_FORBIDDEN)
        package_id = request.data.get('package')
        package = SubscriptionPackage.objects.filter(id=package_id).first()
        if package:
            package.delete()
            return Response({"message": "Package Deleted Successfully"}, status=status.HTTP_200_OK)
        return Response({"message": "Package not found"}, status=status.HTTP_404_NOT_FOUND)

    
class WalletAPIView(APIView):
    '''API Endpoints for Wallets'''
    permission_classes = (permissions.IsAuthenticated,)

    def get(self, request, *args, **kwargs):
        wallets = Wallet.objects.all().order_by('-created_at')
        serializer = WalletSerializer(wallets, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
