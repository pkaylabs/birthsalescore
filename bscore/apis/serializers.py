from django.contrib.auth import authenticate
from rest_framework import serializers

from accounts.models import *
from apis.models import *


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        exclude = ['password', 'groups', 'user_permissions']


class LoginSerializer(serializers.Serializer):
    email = serializers.CharField()
    password = serializers.CharField()

    def validate(self, data):
        user = authenticate(**data)
        if user and user.is_active and ((hasattr(user, "deleted") and user.deleted == False) or not hasattr(user, "deleted")):
            return user
        raise serializers.ValidationError("Incorrect Credentials")


class RegisterUserSerializer(serializers.ModelSerializer):
    """Serializer for user registration."""

    class Meta:
        model = User
        fields = ('email', 'phone', 'password', 'name', 'user_type' )
        extra_kwargs = {
            'password': {'write_only': True},  # Ensure the password is not included in responses
            'email': {'required': True},       # Email is required during registration
            'phone': {'required': True},       # Phone is required during registration
        }

    def validate(self, attrs):
        """Validate the data to ensure the email and phone are unique."""
        if User.objects.filter(email=attrs.get('email')).exists():
            raise serializers.ValidationError("Email already exists")
        if User.objects.filter(phone=attrs.get('phone')).exists():
            raise serializers.ValidationError("Phone already exists")
        return attrs

    def create(self, validated_data):
        """Create a new user instance."""
        user = User.objects.create_user(
            phone=validated_data.get('phone'),
            email=validated_data.get('email'),
            password=validated_data.get('password'),
            name=validated_data.get('name'),
            address=validated_data.get('address'),
            user_type=validated_data.get('user_type'),
        )
        return user

class VendorSerializer(serializers.ModelSerializer):
    user_name = serializers.ReadOnlyField()
    vendor_balance = serializers.ReadOnlyField()
    class Meta:
        model = Vendor
        fields = '__all__'

class WalletSerializer(serializers.ModelSerializer):
    class Meta:
        model = Wallet
        fields = '__all__'

class OTPSerializer(serializers.ModelSerializer):
    class Meta:
        model = OTP
        fields = '__all__'

class SubscriptionPackageSerializer(serializers.ModelSerializer):
    class Meta:
        model = SubscriptionPackage
        fields = '__all__'

class SubscriptionSerializer(serializers.ModelSerializer):
    vendor_name = serializers.ReadOnlyField()
    package_name = serializers.ReadOnlyField()
    expired = serializers.ReadOnlyField()
    payment_status = serializers.ReadOnlyField()
    package_price = serializers.ReadOnlyField()
    class Meta:
        model = Subscription
        fields = '__all__'

class ProductCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductCategory
        fields = '__all__'

class ProductSerializer(serializers.ModelSerializer):
    vendor_name = serializers.ReadOnlyField()
    class Meta:
        model = Product
        fields = '__all__'

class ProductImagesSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductImages
        fields = '__all__'

class ProductReviewSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductReview
        fields = '__all__'

class OrderItemSerializer(serializers.ModelSerializer):
    product_name = serializers.ReadOnlyField()
    class Meta:
        model = OrderItem
        fields = '__all__'

class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)
    payment_status = serializers.ReadOnlyField()
    total_price = serializers.ReadOnlyField()
    vendor_id = serializers.ReadOnlyField()
    customer_name = serializers.ReadOnlyField()
    vendor_name = serializers.ReadOnlyField()
    vendor_phone = serializers.ReadOnlyField()
    class Meta:
        model = Order
        fields = '__all__'

class PlaceOrderSerializer(serializers.ModelSerializer):
    '''Serializer for placing an order'''
    items = OrderItemSerializer(many=True)
    
    class Meta:
        model = Order
        fields = ['user', 'items', 'status', 'location', 'customer_phone']
    
    def create(self, validated_data):
        items_data = validated_data.pop('items')
        # chech if the items are from the same vendor
        vendor_id = items_data[0]['product'].vendor.id
        for item_data in items_data:
            if item_data['product'].vendor.id != vendor_id:
                raise serializers.ValidationError("All items must be from the same vendor")
        order = Order.objects.create(**validated_data)
        order_items = []
        for item_data in items_data:
            product = item_data['product']
            quantity = item_data.get('quantity', 1)
            order_item = OrderItem.objects.create(
                product=product,
                quantity=quantity
            )
            order_items.append(order_item)
        
        # Add all items to the order
        order.items.set(order_items)
        return order

class ServiceBookingSerializer(serializers.ModelSerializer):
    '''Serializer for service booking'''
    service_name = serializers.ReadOnlyField()
    user_name = serializers.ReadOnlyField()
    vendor_name = serializers.ReadOnlyField()
    user_phone = serializers.ReadOnlyField()
    vendor_phone = serializers.ReadOnlyField()

    class Meta:
        model = ServiceBooking
        fields = '__all__'

class ServiceSerializer(serializers.ModelSerializer):
    vendor = VendorSerializer(read_only=True)
    bookings = serializers.SerializerMethodField()

    def get_bookings(self, obj):
        bookings = ServiceBooking.objects.filter(service=obj).count()
        return bookings
    
    class Meta:
        model = Service
        fields = '__all__'

class AdSerializer(serializers.ModelSerializer):
    class Meta:
        model = Ad
        fields = '__all__'

class BannerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Banner
        fields = '__all__'

class AdImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = AdImage
        fields = '__all__'

class PaymentSerializer(serializers.ModelSerializer):
    customer_name = serializers.ReadOnlyField()
    what_was_paid_for = serializers.ReadOnlyField()
    class Meta:
        model = Payment
        fields = '__all__'

class ChangePasswordSerializer(serializers.Serializer):
    '''Serializer for changing password'''
    old_password = serializers.CharField()
    new_password = serializers.CharField()
    confirm_password = serializers.CharField()

    def validate(self, data):
        if data.get('new_password') != data.get('confirm_password'):
            raise serializers.ValidationError("Passwords do not match")
        return data

class ResetPasswordSerializer(serializers.Serializer):
    '''Serializer for resetting password'''
    phone = serializers.CharField()
    new_password = serializers.CharField()
    confirm_password = serializers.CharField()

    def validate(self, data):
        if not User.objects.filter(phone=data.get('phone')).exists():
            raise serializers.ValidationError("Phone does not exist")
        return data