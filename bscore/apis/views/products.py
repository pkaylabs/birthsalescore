from rest_framework import status, permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from apis.models import Order, Product, ProductCategory
from apis.serializers import OrderSerializer, ProductCategorySerializer, ProductSerializer
from bscore.utils.const import UserType
from bscore.utils.permissions import IsSuperuser, IsAdminOnly, IsCustomerOnly, IsEliteVendorOnly

class ProductAPIView(APIView):
    '''API Endpoints for Products'''

    permission_classes = (permissions.IsAuthenticated,)

    def get(self, request, *args, **kwargs):
        user = request.user

        if user.is_superuser or user.user_type == UserType.ADMIN.value:
            products = Product.objects.all().order_by('-created_at')
        elif user.user_type == UserType.VENDOR.value:
            products = Product.objects.filter(vendor=user.vendor_profile).order_by('-created_at')
        else:
            products = Product.objects.filter(is_active=True).order_by('-created_at')

        serializer = ProductSerializer(products, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request, *args, **kwargs):
        '''Create a new product''' 
        user = request.user
        if user.user_type != UserType.VENDOR.value:
            return Response({"message": "Only vendors can add products"}, status=status.HTTP_403_FORBIDDEN)
        
        serializer = ProductSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(vendor=user.vendor_profile)
            return Response({"message": "Product created successfully", "product": serializer.data}, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def put(self, request, *args, **kwargs):
        '''Update a product (Only vendor who owns it can update)'''
        user = request.user
        product_id = request.data.get('product_id')
        product = Product.objects.filter(id=product_id, vendor=user.vendor_profile).first()

        if not product:
            return Response({"message": "Product not found or permission denied"}, status=status.HTTP_404_NOT_FOUND)
        
        serializer = ProductSerializer(product, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response({"message": "Product updated successfully", "product": serializer.data}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, *args, **kwargs):
        '''Delete a product (Only vendor who owns it can delete)'''
        user = request.user
        product_id = request.data.get('product_id')
        product = Product.objects.filter(id=product_id, vendor=user.vendor_profile).first()

        if not product:
            return Response({"message": "Product not found or permission denied"}, status=status.HTTP_404_NOT_FOUND)
        
        product.delete()
        return Response({"message": "Product deleted successfully"}, status=status.HTTP_200_OK)


class ProductCategoryAPIView(APIView):
    '''API Endpoints for Product Categories'''
    permission_classes = (permissions.IsAuthenticated,)

    def get(self, request, *args, **kwargs):
        categories = ProductCategory.objects.all()
        serializer = ProductCategorySerializer(categories, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request, *args, **kwargs):
        serializer = ProductCategorySerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response({"message": "Category created successfully", "category": serializer.data}, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, *args, **kwargs):
        category_id = request.data.get('category_id')
        category = ProductCategory.objects.filter(id=category_id).first()
        if not category:
            return Response({"message": "Category not found"}, status=status.HTTP_404_NOT_FOUND)
        category.delete()
        return Response({"message": "Category deleted successfully"}, status=status.HTTP_200_OK)
    
    
class OrderAPIView(APIView):
    '''API Endpoints for Orders (Read-only)'''
    permission_classes = (permissions.IsAuthenticated,)

    def get(self, request, *args, **kwargs):
        orders = Order.objects.all().order_by('-created_at')
        serializer = OrderSerializer(orders, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)