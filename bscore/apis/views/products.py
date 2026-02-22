from django.db.models import Avg, Count, Q
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from drf_spectacular.utils import extend_schema, OpenApiExample, OpenApiResponse

from accounts.models import Vendor
from apis.models import (Order, Product, ProductCategory, Service,
                    ServiceBooking, ProductRating)
from apis.utils.querysets import filter_products_for_public
from apis.serializers import (OrderSerializer, PlaceOrderSerializer,
                              ProductCategorySerializer, ProductSerializer,
                        ServiceBookingSerializer, ServiceSerializer,
                        ProductRatingSerializer)
from bscore.utils.const import UserType


class ProductAPIView(APIView):
    '''API Endpoints for Products'''

    permission_classes = (permissions.IsAuthenticated,)

    def get(self, request, *args, **kwargs):
        user = request.user

        if user.is_superuser or user.user_type == UserType.ADMIN.value:
            products = Product.objects.all().order_by('-created_at')
        elif user.user_type == UserType.VENDOR.value:
            vendor = Vendor.objects.filter(user=user).first()
            if vendor and vendor.has_active_subscription() and vendor.can_create_or_view_product():
                products = Product.objects.filter(vendor__vendor_id=user.vendor_profile['vendor_id']).order_by('-created_at')
            else:
                return Response({"message": "Vendor profile not found or subscription expired"}, status=status.HTTP_400_BAD_REQUEST)
        else:
            # For customers/other users, exclude products from vendors with expired subscriptions.
            products = filter_products_for_public(Product.objects.all()).order_by('-created_at')

        serializer = ProductSerializer(products, many=True, context={"request": request})
        return Response(serializer.data, status=status.HTTP_200_OK)

    @extend_schema(
        summary='Create a product (vendor/admin)',
        description=(
            'Supports extra features via `available_colors` and `available_sizes`. '
            'If you are uploading `image`, use `multipart/form-data`. '
            'In multipart, you can pass `available_colors`/`available_sizes` as JSON string (e.g. `["Red","Blue"]`) '
            'or as comma-separated string (e.g. `Red,Blue`).'
        ),
        request={
            'multipart/form-data': {
                'type': 'object',
                'properties': {
                    'name': {'type': 'string'},
                    'description': {'type': 'string'},
                    'price': {'type': 'string'},
                    'category': {'type': 'integer'},
                    'in_stock': {'type': 'boolean'},
                    'is_published': {'type': 'boolean'},
                    'image': {'type': 'string', 'format': 'binary'},
                    'available_colors': {'type': 'string', 'description': 'JSON list string or comma-separated string'},
                    'available_sizes': {'type': 'string', 'description': 'JSON list string or comma-separated string'},
                    'vendor': {'type': 'integer', 'description': 'Admin-only: vendor DB id'},
                },
                'required': ['name', 'price', 'category'],
            },
            'application/json': {
                'type': 'object',
                'properties': {
                    'name': {'type': 'string'},
                    'description': {'type': 'string'},
                    'price': {'type': 'string'},
                    'category': {'type': 'integer'},
                    'in_stock': {'type': 'boolean'},
                    'is_published': {'type': 'boolean'},
                    'available_colors': {'type': 'array', 'items': {'type': 'string'}},
                    'available_sizes': {'type': 'array', 'items': {'type': 'string'}},
                    'vendor': {'type': 'integer', 'description': 'Admin-only: vendor DB id'},
                },
                'required': ['name', 'price', 'category'],
            },
        },
        responses={
            201: OpenApiResponse(description='Created'),
            400: OpenApiResponse(description='Validation error'),
            401: OpenApiResponse(description='Authentication required'),
        },
        examples=[
            OpenApiExample(
                'Create Product (JSON arrays)',
                value={
                    'name': 'Baby Diapers',
                    'description': 'Size 1 diapers',
                    'price': '25.00',
                    'category': 2,
                    'in_stock': True,
                    'is_published': True,
                    'available_colors': ['White', 'Blue'],
                    'available_sizes': ['S', 'M'],
                },
                request_only=True,
            ),
            OpenApiExample(
                'Create Product (multipart strings)',
                value={
                    'name': 'Maternity Dress',
                    'price': '120.00',
                    'category': 3,
                    'available_colors': '["Black","Wine"]',
                    'available_sizes': 'S,M,L',
                    'image': '(binary)',
                },
                request_only=True,
            ),
            OpenApiExample(
                'Create Product Response',
                value={
                    'message': 'Product created successfully',
                    'product': {
                        'id': 1,
                        'name': 'Baby Diapers',
                        'description': 'Size 1 diapers',
                        'price': '25.00',
                        'category': 2,
                        'in_stock': True,
                        'is_published': True,
                        'available_colors': ['White', 'Blue'],
                        'available_sizes': ['S', 'M'],
                        'image': 'http://localhost:8000/media/products/diapers.png',
                        'created_at': '2026-02-20T12:00:00Z',
                        'updated_at': '2026-02-20T12:00:00Z',
                    },
                },
                response_only=True,
            ),
        ],
    )
    def post(self, request, *args, **kwargs):
        '''Create a new product''' 
        user = request.user
        vendor = Vendor.objects.filter(user=user).first()
        if user.is_superuser or user.is_staff or user.user_type == UserType.ADMIN.value:
            vendor_id = request.POST.get('vendor')
            if vendor_id:
                vendor = Vendor.objects.filter(id=vendor_id).first()
        # check if vendor has active subscription and can create or view product
        if not (vendor and vendor.has_active_subscription() and vendor.can_create_or_view_product()):
            return Response({"message": "Vendor profile not found or subscription expired"}, status=status.HTTP_400_BAD_REQUEST)
        serializer = ProductSerializer(data=request.data, context={"request": request})
        if serializer.is_valid():
            if vendor:
                serializer.validated_data['vendor'] = vendor
            else:
                return Response({"message": "Vendor profile not found"}, status=status.HTTP_400_BAD_REQUEST)
            serializer.save()
            return Response({"message": "Product created successfully", "product": serializer.data}, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @extend_schema(
        summary='Update a product (vendor/admin)',
        description='Send `product_id` in the body. Supports updating `available_colors` and `available_sizes` (arrays or strings).',
        request={
            'multipart/form-data': {
                'type': 'object',
                'properties': {
                    'product_id': {'type': 'integer'},
                    'name': {'type': 'string'},
                    'description': {'type': 'string'},
                    'price': {'type': 'string'},
                    'category': {'type': 'integer'},
                    'in_stock': {'type': 'boolean'},
                    'is_published': {'type': 'boolean'},
                    'image': {'type': 'string', 'format': 'binary'},
                    'available_colors': {'type': 'string'},
                    'available_sizes': {'type': 'string'},
                },
                'required': ['product_id'],
            },
            'application/json': {
                'type': 'object',
                'properties': {
                    'product_id': {'type': 'integer'},
                    'name': {'type': 'string'},
                    'description': {'type': 'string'},
                    'price': {'type': 'string'},
                    'category': {'type': 'integer'},
                    'in_stock': {'type': 'boolean'},
                    'is_published': {'type': 'boolean'},
                    'available_colors': {'type': 'array', 'items': {'type': 'string'}},
                    'available_sizes': {'type': 'array', 'items': {'type': 'string'}},
                },
                'required': ['product_id'],
            },
        },
        responses={
            200: OpenApiResponse(description='Updated'),
            400: OpenApiResponse(description='Validation error'),
            401: OpenApiResponse(description='Authentication required'),
            404: OpenApiResponse(description='Product not found'),
        },
        examples=[
            OpenApiExample(
                'Update Product Features',
                value={
                    'product_id': 1,
                    'available_colors': ['Black', 'White'],
                    'available_sizes': ['L', 'XL'],
                },
                request_only=True,
            ),
            OpenApiExample(
                'Update Product (multipart strings)',
                value={
                    'product_id': 1,
                    'available_colors': 'Black, White',
                    'available_sizes': '["L","XL"]',
                    'image': '(binary)',
                },
                request_only=True,
            ),
            OpenApiExample(
                'Update Product Response',
                value={
                    'message': 'Product updated successfully',
                    'product': {
                        'id': 1,
                        'name': 'Baby Diapers',
                        'available_colors': ['Black', 'White'],
                        'available_sizes': ['L', 'XL'],
                        'updated_at': '2026-02-20T12:30:00Z',
                    },
                },
                response_only=True,
            ),
        ],
    )
    def put(self, request, *args, **kwargs):
        '''Update a product (Only vendor who owns it can update)'''
        user = request.user
        vendor = Vendor.objects.filter(user=user).first()
        product_id = request.data.get('product_id')
        if user.is_superuser or user.is_staff or user.user_type == UserType.ADMIN.value:
           product = Product.objects.filter(id=product_id).first()
        else:
            # check if vendor has active subscription and can create or view product
            if not (vendor and vendor.has_active_subscription() and vendor.can_create_or_view_product()):
                return Response({"message": "Vendor profile not found or subscription expired"}, status=status.HTTP_400_BAD_REQUEST)
            product = Product.objects.filter(id=product_id, vendor=vendor).first()

        if not product:
            return Response({"message": "Product not found"}, status=status.HTTP_404_NOT_FOUND)
        
        serializer = ProductSerializer(product, data=request.data, partial=True, context={"request": request})
        if serializer.is_valid():
            serializer.save()
            return Response({"message": "Product updated successfully", "product": serializer.data}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @extend_schema(
        summary='Delete a product (vendor/admin)',
        request={
            'application/json': {
                'type': 'object',
                'properties': {
                    'product_id': {'type': 'integer'},
                },
                'required': ['product_id'],
            }
        },
        responses={
            200: OpenApiResponse(description='Deleted'),
            400: OpenApiResponse(description='Validation error'),
            401: OpenApiResponse(description='Authentication required'),
            404: OpenApiResponse(description='Product not found'),
        },
        examples=[
            OpenApiExample('Delete Product', value={'product_id': 1}, request_only=True),
            OpenApiExample(
                'Delete Product Response',
                value={'message': 'Product deleted successfully'},
                response_only=True,
            ),
        ],
    )
    def delete(self, request, *args, **kwargs):
        '''Delete a product (Only vendor who owns it can delete)'''
        user = request.user
        vendor = Vendor.objects.filter(user=user).first()
        product_id = request.data.get('product_id')
        if user.is_superuser or user.is_staff or user.user_type == UserType.ADMIN.value:
            product = Product.objects.filter(id=product_id).first()
        else:
            # check if vendor has active subscription and can create or view product
            if not (vendor and vendor.has_active_subscription() and vendor.can_create_or_view_product()):
                return Response({"message": "Vendor profile not found or subscription expired"}, status=status.HTTP_400_BAD_REQUEST)
            product = Product.objects.filter(id=product_id, vendor=vendor).first()

        if not product:
            return Response({"message": "Product not found or permission denied"}, status=status.HTTP_404_NOT_FOUND)
        
        product.delete()
        return Response({"message": "Product deleted successfully"}, status=status.HTTP_200_OK)


class CustomerProductsAPIView(APIView):
    '''API Endpoints for to get products for customers'''

    permission_classes = (permissions.AllowAny,)

    def get(self, request, *args, **kwargs):
        '''Get all products for customers'''
        query = request.query_params.get('query', None)
        products_qs = filter_products_for_public(Product.objects.filter(is_published=True))

        if query and query.isdigit():
            products = products_qs.filter(id=int(query)).first()
            many = False
        else:
            products = products_qs.order_by('-created_at')
            many = True
        if query and not products:
            return Response({"message": "No products found"}, status=status.HTTP_404_NOT_FOUND)
        serializer = ProductSerializer(products, many=many, context={"request": request})
        return Response(serializer.data, status=status.HTTP_200_OK)


class CustomerServicesAPIView(APIView):
    '''API Endpoints for to get products for customers'''

    permission_classes = (permissions.AllowAny,)

    def get(self, request, *args, **kwargs):
        '''Get all services for customers'''
        query = request.query_params.get('query', None)
        if query and query.isdigit():
            # filter services based on query 
            # | exclude vendors with no active subscription
            # | exclude services that are not published
            services = Service.objects.filter(published=True)
            service_ids = [
                service.id for service in services if service.vendor.has_active_subscription() and service.vendor.can_create_or_view_service()
            ]
            print("Query: ", query)
            print("Serice IDs: ", service_ids)
            services = Service.objects.filter(id__in=service_ids).filter(id=query).first()
            print("Services: ", services)
            many = False
        else:
            # get all services
            services = Service.objects.filter(published=True)

            service_ids = [
                service.id for service in services if service.vendor.has_active_subscription() and service.vendor.can_create_or_view_service()
            ]
            print("Service IDs: ", service_ids)
            services = Service.objects.filter(id__in=service_ids).order_by('-created_at')
            print("Services: ", services)
            many = True
        if query and not services:
            return Response({"message": "No services found"}, status=status.HTTP_404_NOT_FOUND)
        serializer = ServiceSerializer(services, many=many)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
class ProductSearchAPIView(APIView):
    '''API Endpoints for searching products'''

    permission_classes = (permissions.AllowAny,)

    def get(self, request, *args, **kwargs):
        '''Get all products for customers'''
        query = request.query_params.get('query', None)
        products = filter_products_for_public(Product.objects.filter(is_published=True))
        if query:
            products = products.filter(
                Q(name__icontains=query) | Q(description__icontains=query) | Q(category__name__icontains=query)
            )

        products = products.order_by('-created_at')
        serializer = ProductSerializer(products, many=True, context={"request": request})
        return Response(serializer.data, status=status.HTTP_200_OK)


class ProductRatingsAPIView(APIView):
    """List ratings for a product and allow customers to create/update their rating."""

    permission_classes = (permissions.AllowAny,)

    def get(self, request, *args, **kwargs):
        product_id = request.query_params.get('product_id')
        if not product_id:
            return Response({"message": "product_id is required"}, status=status.HTTP_400_BAD_REQUEST)

        ratings = ProductRating.objects.filter(product_id=product_id).select_related('user').order_by('-created_at')
        serializer = ProductRatingSerializer(ratings, many=True, context={"request": request})
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return Response({"message": "Authentication required"}, status=status.HTTP_401_UNAUTHORIZED)
        if getattr(request.user, 'user_type', None) != UserType.CUSTOMER.value:
            return Response({"message": "Only customers can rate products"}, status=status.HTTP_403_FORBIDDEN)

        serializer = ProductRatingSerializer(data=request.data, context={"request": request})
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        product = serializer.validated_data.get('product')
        rating_value = serializer.validated_data.get('rating')
        comment = serializer.validated_data.get('comment')

        has_ordered = Order.objects.filter(
            user=request.user,
            items__product=product,
        ).exclude(status='Cancelled').exists()

        if not has_ordered:
            return Response(
                {"message": "Only customers who have ordered this product can rate it"},
                status=status.HTTP_403_FORBIDDEN,
            )

        rating_obj, _ = ProductRating.objects.update_or_create(
            product=product,
            user=request.user,
            defaults={"rating": rating_value, "comment": comment},
        )

        agg = ProductRating.objects.filter(product=product).aggregate(
            avg=Avg('rating'),
            cnt=Count('id'),
        )
        avg = agg.get('avg')
        average_rating = round(float(avg), 2) if avg is not None else None
        ratings_count = int(agg.get('cnt') or 0)

        rating_data = ProductRatingSerializer(rating_obj, context={"request": request}).data
        rating_data["average_rating"] = average_rating
        rating_data["ratings_count"] = ratings_count
        return Response(rating_data, status=status.HTTP_200_OK)

    def put(self, request, *args, **kwargs):
        return self.post(request, *args, **kwargs)

    def patch(self, request, *args, **kwargs):
        return self.post(request, *args, **kwargs)

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
            
        elif user.user_type == UserType.CUSTOMER.value or user.user_type == UserType.DELIVERY.value:
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
        user = request.user
        if user.is_superuser or user.is_staff or user.user_type == UserType.ADMIN.value:
            # admin users get to see all services
            services = Service.objects.all().order_by('-created_at')
        elif user.user_type == UserType.VENDOR.value:
            # vendors get to see only their services
            vendor = Vendor.objects.filter(user=user).first()
            if vendor and vendor.has_active_subscription() and vendor.can_create_or_view_product():
                services = Service.objects.filter(vendor=vendor).order_by('-created_at')
            else:
                return Response({"message": "Vendor profile not found or subscription expired"}, status=status.HTTP_400_BAD_REQUEST)
        else:
            services = Service.objects.none()
        serializer = ServiceSerializer(services, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    def post(self, request, *args, **kwargs):
        '''create new services -- vendors and admins'''
        user = request.user
        vendor = Vendor.objects.filter(user=user).first()
        vendor_id = request.POST.get('vendor_id')
        if vendor_id and not vendor:
            vendor = Vendor.objects.filter(vendor_id=vendor_id).first()
        
        if not (vendor and vendor.has_active_subscription() and vendor.can_create_or_view_product()):
            return Response({"message": "Vendor profile not found or subscription expired"}, status=status.HTTP_400_BAD_REQUEST)
        
        serializer = ServiceSerializer(data=request.data)

        if serializer.is_valid():
            service = serializer.save(vendor=vendor)
            return Response(ServiceSerializer(service).data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    def put(self, request, *args, **kwargs):
        '''
            Update Service endpoint.
            We're using this to publish a service.
            Only admins can publish a service.
        '''
        user = request.user
        service_id = request.data.get('service_id')
        if user.is_superuser or user.is_staff or user.user_type == UserType.ADMIN.value:
           service = Service.objects.filter(id=service_id).first()
           if not service:
               return Response({"error": "Service not found"}, status=status.HTTP_404_NOT_FOUND)
           service.published = True
           service.save()
           serializer = ServiceSerializer(service)
           return Response({"message": "Service Published Successfully", "service": serializer.data}, status=status.HTTP_200_OK)
        else:
            return Response({"message": "You are not allowed to access this page"}, status=status.HTTP_403_FORBIDDEN)

    

    def delete(self, request, *args, **kwargs):
        '''delete a service'''
        user = request.user
        service_id = request.data.get('service')
        if user.is_superuser or user.is_staff or user.user_type == UserType.ADMIN.value:
            service = Service.objects.filter(id=service_id).first()
        else:
            vendor = Vendor.objects.filter(user=user).first()
            if vendor and vendor.has_active_subscription() and vendor.can_create_or_view_product():
                service = Service.objects.filter(vendor=vendor, id=service_id).first()
            else:
                return Response({"message": "Vendor profile not found or subscription expired"}, status=status.HTTP_400_BAD_REQUEST)
        
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
        elif user.user_type == UserType.CUSTOMER.value or user.user_type == UserType.DELIVERY.value:
            # customers get to see only their bookings
            bookings = ServiceBooking.objects.filter(user=user).order_by('-created_at')
        else:
            # any other user type sees empty list for now.
            bookings = ServiceBooking.objects.none()
        serializer = ServiceBookingSerializer(bookings, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    def put(self, request, *args, **kwargs):
        '''update a booking'''
        user = request.user
        booking_id = request.data.get('booking')
        if user.is_superuser or user.is_staff or user.user_type == UserType.ADMIN.value:
            booking = ServiceBooking.objects.filter(id=booking_id).first()
        else:
            vendor = Vendor.objects.filter(user=user).first()
            booking = ServiceBooking.objects.filter(service__vendor=vendor, id=booking_id).first()
        print("Booking ID: ", booking_id)
        print("Booking: ", booking)
        if booking is None:
            return Response({"error": "Booking not found"}, status=status.HTTP_404_NOT_FOUND)
        
        serializer = ServiceBookingSerializer(booking, data=request.data, partial=True)
        if serializer.is_valid():
            booking = serializer.save()
            return Response({
                "message": "Booking updated successfully",
                "data": ServiceBookingSerializer(booking).data
            }, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    def post(self, request, *args, **kwargs):
        '''create/book a new service'''
        user = request.user
        req_data = request.data.copy()
        req_data['user'] = user.id
        serializer = ServiceBookingSerializer(data=req_data)

        if serializer.is_valid():
            booking = serializer.save()
            return Response({
                "message": "Booking created successfully",
                "data": ServiceBookingSerializer(booking).data
            }, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
class PlaceOrderAPIView(APIView):
    '''Endpoint to place an order'''

    permission_classes = (permissions.IsAuthenticated,)

    @extend_schema(
        summary='Place an order (location required)',
        description='`location` is a single unified field: pass a Location id (e.g. "1") or a Location name (e.g. "Hall A").',
        request=PlaceOrderSerializer,
        responses={
            201: OpenApiResponse(description='Order placed successfully'),
            400: OpenApiResponse(description='Validation error'),
            401: OpenApiResponse(description='Authentication required'),
        },
        examples=[
            OpenApiExample(
                'Place Order',
                value={
                    "items": [
                        {"product": 1, "quantity": 1, "color": "Black", "size": "M"},
                        {"product": 2, "quantity": 2}
                    ],
                    "location": "1",
                    "customer_phone": "+233501234567"
                },
                request_only=True,
            ),
        ],
    )
    def post(self, request, *args, **kwargs):
        user = request.user
      
        req_data = request.data.copy()
        req_data['user'] = user.id
        serializer = PlaceOrderSerializer(data=req_data)
        if serializer.is_valid():
            order = serializer.save()
            # notify vendor and customer
            order.notify_vendor_and_customer()
            return Response({ "message": "Order Placed Successfully",  "data": OrderSerializer(order).data}, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)