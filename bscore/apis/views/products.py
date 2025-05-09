from django.db.models import Q
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import Vendor
from apis.models import (Order, Product, ProductCategory, Service,
                         ServiceBooking)
from apis.serializers import (OrderSerializer, PlaceOrderSerializer,
                              ProductCategorySerializer, ProductSerializer,
                              ServiceBookingSerializer, ServiceSerializer)
from bscore.utils.const import UserType


class ProductAPIView(APIView):
    '''API Endpoints for Products'''

    permission_classes = (permissions.IsAuthenticated,)

    def get(self, request, *args, **kwargs):
        user = request.user

        if user.is_superuser or user.user_type == UserType.ADMIN.value:
            products = Product.objects.all().order_by('-created_at')
        elif user.user_type == UserType.VENDOR.value:
            products = Product.objects.filter(vendor__vendor_id=user.vendor_profile['vendor_id']).order_by('-created_at')
        else:
            products = Product.objects.filter(is_active=True).order_by('-created_at')

        serializer = ProductSerializer(products, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request, *args, **kwargs):
        '''Create a new product''' 
        user = request.user
        # if user.user_type != UserType.VENDOR.value :
        #     return Response({"message": "Only vendors can add products"}, status=status.HTTP_403_FORBIDDEN)
        vendor = Vendor.objects.filter(user=user).first()
        if user.is_superuser or user.is_staff or user.user_type == UserType.ADMIN.value:
            vendor_id = request.POST.get('vendor')
            if vendor_id:
                vendor = Vendor.objects.filter(id=vendor_id).first()
        
        serializer = ProductSerializer(data=request.data)
        if serializer.is_valid():
            if vendor:
                serializer.validated_data['vendor'] = vendor
            else:
                return Response({"message": "Vendor profile not found"}, status=status.HTTP_400_BAD_REQUEST)
            serializer.save()
            return Response({"message": "Product created successfully", "product": serializer.data}, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def put(self, request, *args, **kwargs):
        '''Update a product (Only vendor who owns it can update)'''
        user = request.user
        vendor = Vendor.objects.filter(user=user).first()
        product_id = request.data.get('product_id')
        if user.is_superuser or user.is_staff or user.user_type == UserType.ADMIN.value:
           product = Product.objects.filter(id=product_id).first()
        else:
            product = Product.objects.filter(id=product_id, vendor=vendor).first()

        if not product:
            return Response({"message": "Product not found"}, status=status.HTTP_404_NOT_FOUND)
        
        serializer = ProductSerializer(product, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response({"message": "Product updated successfully", "product": serializer.data}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, *args, **kwargs):
        '''Delete a product (Only vendor who owns it can delete)'''
        user = request.user
        vendor = Vendor.objects.filter(user=user).first()
        product_id = request.data.get('product_id')
        if user.is_superuser or user.is_staff or user.user_type == UserType.ADMIN.value:
            product = Product.objects.filter(id=product_id).first()
        else:
            product = Product.objects.filter(id=product_id, vendor=vendor).first()

        if not product:
            return Response({"message": "Product not found or permission denied"}, status=status.HTTP_404_NOT_FOUND)
        
        product.delete()
        return Response({"message": "Product deleted successfully"}, status=status.HTTP_200_OK)


class CustomersProductAPIView(APIView):
    '''API Endpoints for to get products for customers'''

    permission_classes = (permissions.AllowAny,)

    def get(self, request, *args, **kwargs):
        '''Get all products for customers'''
        query = request.query_params.get('query', None)
        if query and query.isdigit():
            # filter products based on query
            products = Product.objects.filter(is_published=True, id=query).first()
            many = False
        else:
            # get all products
            products = Product.objects.filter(is_published=True).order_by('-created_at')
            many = True
        if query and not products:
            return Response({"message": "No products found"}, status=status.HTTP_404_NOT_FOUND)
        if query and products:
            serializer = ProductSerializer(products, many=False)
            return Response(serializer.data, status=status.HTTP_200_OK)
        # filter products based on query
        serializer = ProductSerializer(products, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
class ProductSearchAPIView(APIView):
    '''API Endpoints for searching products'''

    permission_classes = (permissions.AllowAny,)

    def get(self, request, *args, **kwargs):
        '''Get all products for customers'''
        query = request.query_params.get('query', None)
        if query:
            # filter products based on query
            products = Product.objects.filter(
                Q(name__icontains=query) | Q(description__icontains=query) | Q(category__name__icontains=query),
                is_published=True
            ).order_by('-created_at')
        else:
            # get all products
            products = Product.objects.filter(is_published=True).order_by('-created_at')
        serializer = ProductSerializer(products, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

class ProductCategoryAPIView(APIView):
    '''API Endpoints for Product Categories'''
    permission_classes = (permissions.IsAuthenticated,)

    def get(self, request, *args, **kwargs):
        categories = ProductCategory.objects.all()
        serializer = ProductCategorySerializer(categories, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request, *args, **kwargs):
        # only admins can create categories
        if not request.user.is_superuser and not request.user.is_staff and request.user.user_type != UserType.ADMIN.value:
            return Response({"message": "Only admins can create categories"}, status=status.HTTP_403_FORBIDDEN)
        serializer = ProductCategorySerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response({"message": "Category created successfully", "category": serializer.data}, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, *args, **kwargs):
        # only admins can delete categories
        if not request.user.is_superuser and not request.user.is_staff and request.user.user_type != UserType.ADMIN.value:
            return Response({"message": "Only admins can delete categories"}, status=status.HTTP_403_FORBIDDEN)
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
        '''Get orders based on user role'''
        user = request.user
        
        if user.is_superuser or user.is_staff or user.user_type == UserType.ADMIN.value:
            # ADMIN: See all orders
            orders = Order.objects.all()
            
        elif user.user_type == UserType.VENDOR.value:
            # VENDOR: See orders containing THEIR products
            orders = Order.objects.filter(
                items__product__vendor__user=user  # Orders with items from this vendor
            ).distinct()  # Avoid duplicates if order has multiple items from same vendor
            
        elif user.user_type == UserType.CUSTOMER.value:
            # CUSTOMER: See only THEIR OWN orders
            orders = Order.objects.filter(user=user)
            
        else:
            # Other user types see nothing
            orders = Order.objects.none()

        # Optimize queries using prefetch_related and select_related
        # This will reduce the number of queries made to the database
        orders = orders.select_related('user').prefetch_related(
            'items',
            'items__product',
            'items__product__vendor',
            'items__product__vendor__user'
        ).order_by('-created_at')

        serializer = OrderSerializer(orders, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class ServicesAPIView(APIView):
    '''Endpoint to get and create services'''

    permission_classes = (permissions.IsAuthenticated,)

    def get(self, request, *args,**kwargs):
        '''gets available services'''
        services = Service.objects.all().order_by('-created_at')
        serializer = ServiceSerializer(services, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    def post(self, request, *args, **kwargs):
        '''create new services -- vendors and admins'''
        user = request.user
        vendor = Vendor.objects.filter(user=user).first()
        vendor_id = request.POST.get('vendor_id')
        if vendor_id and not vendor:
            vendor = Vendor.objects.filter(vendor_id=vendor_id).first()
        
        if not vendor:
            return Response({"error": "A vendor profile is required"}, status=status.HTTP_400_BAD_REQUEST)
        
        serializer = ServiceSerializer(data=request.data)

        if serializer.is_valid():
            service = serializer.save(vendor=vendor)
            return Response(ServiceSerializer(service).data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    

    def delete(self, request, *args, **kwargs):
        '''delete a service'''
        user = request.user
        service_id = request.data.get('service')
        if user.is_superuser or user.is_staff or user.user_type == UserType.ADMIN.value:
            service = Service.objects.filter(id=service_id).first()
        else:
            vendor = Vendor.objects.filter(user=user).first()
            service = Service.objects.filter(vendor=vendor, id=service_id).first()
        
        if not service:
            return Response({"error": "Service not found"}, status=status.HTTP_404_NOT_FOUND)
        service.delete()
        return Response({"message": "Service Deleted Successfully"}, status=status.HTTP_200_OK)


class BookingsAPIView(APIView):
    '''Endpoint to get and create bookings'''

    permission_classes = (permissions.IsAuthenticated,)

    def get(self, request, *args, **kwargs):
        '''gets available services'''
        user = request.user
        # admin users get to see all bookings
        if user.is_superuser or user.is_staff or user.user_type == UserType.ADMIN.value:
            bookings = ServiceBooking.objects.all().order_by('-created_at')
        elif user.user_type == UserType.VENDOR.value:
            # vendors get to see only the bookings for their services
            vendor = Vendor.objects.filter(user=user).first()
            bookings = ServiceBooking.objects.filter(service__vendor=vendor).order_by('-created_at')
        else:
            # any other user type sees empty list for now.
            bookings = ServiceBooking.objects.none()
        serializer = ServiceBookingSerializer(bookings, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
class PlaceOrderAPIView(APIView):
    '''Endpoint to place an order'''

    permission_classes = (permissions.IsAuthenticated,)

    def post(self, request, *args, **kwargs):
        user = request.user
      
        req_data = request.data.copy()
        req_data['user'] = user.id
        serializer = PlaceOrderSerializer(data=req_data)
        if serializer.is_valid():
            order = serializer.save()
            return Response({ "message": "Order Placed Successfully",  "data": OrderSerializer(order).data}, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)