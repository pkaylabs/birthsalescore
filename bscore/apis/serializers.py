import json

from django.conf import settings
from django.contrib.auth import authenticate
from rest_framework import serializers

from accounts.models import *
from apis.models import *


def _to_absolute_url(*, request, url: str | None) -> str | None:
    if not url:
        return None
    if url.startswith('http://') or url.startswith('https://'):
        return url
    if request is not None:
        return request.build_absolute_uri(url)
    base_url = getattr(settings, 'PUBLIC_BASE_URL', None)
    if base_url:
        return base_url.rstrip('/') + '/' + url.lstrip('/')
    return url



class UserSerializer(serializers.ModelSerializer):
    avatar = serializers.SerializerMethodField()

    def get_avatar(self, obj):
        request = self.context.get('request')
        if not getattr(obj, 'avatar', None):
            return None
        try:
            url = obj.avatar.url
        except Exception:
            return None
        return _to_absolute_url(request=request, url=url)

    class Meta:
        model = User
        exclude = ['password', 'groups', 'user_permissions']


class UserAvatarSerializer(serializers.ModelSerializer):
    avatar = serializers.SerializerMethodField()

    def get_avatar(self, obj):
        request = self.context.get('request')
        if not getattr(obj, 'avatar', None):
            return None
        try:
            url = obj.avatar.url
        except Exception:
            return None
        return _to_absolute_url(request=request, url=url)

    class Meta:
        model = User
        fields = ['avatar']


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
    images = serializers.SerializerMethodField()

    def _normalize_str_list(self, value):
        if value is None:
            return []
        if isinstance(value, str):
            value = value.strip()
            if not value:
                return []
            # Accept JSON list string or comma-separated values.
            try:
                loaded = json.loads(value)
                if isinstance(loaded, list):
                    value = loaded
                else:
                    value = [value]
            except Exception:
                value = [v.strip() for v in value.split(',')]

        if isinstance(value, (tuple, list)):
            normalized = []
            seen = set()
            for item in value:
                if item is None:
                    continue
                s = str(item).strip()
                if not s:
                    continue
                key = s.lower()
                if key in seen:
                    continue
                seen.add(key)
                normalized.append(s)
            return normalized

        return [str(value).strip()] if str(value).strip() else []

    def validate(self, attrs):
        attrs = super().validate(attrs)
        if 'available_colors' in attrs:
            attrs['available_colors'] = self._normalize_str_list(attrs.get('available_colors'))
        if 'available_sizes' in attrs:
            attrs['available_sizes'] = self._normalize_str_list(attrs.get('available_sizes'))
        return attrs

    def get_images(self, obj):
        # Return extra images with absolute URLs.
        # Use serializer context so FileField can build absolute URLs when request is available.
        images_qs = getattr(obj, 'images', None)
        if images_qs is None:
            return []
        serializer = ProductImagesSerializer(images_qs.all(), many=True, context=self.context)
        return serializer.data

    def to_representation(self, instance):
        rep = super().to_representation(instance)
        request = self.context.get('request')
        # Product.image comes out as a URL string (or null). Convert to absolute.
        rep['image'] = _to_absolute_url(request=request, url=rep.get('image'))
        # Only return features if present.
        rep['available_colors'] = rep.get('available_colors') or None
        rep['available_sizes'] = rep.get('available_sizes') or None
        return rep
    class Meta:
        model = Product
        fields = '__all__'

class ProductImagesSerializer(serializers.ModelSerializer):
    image = serializers.SerializerMethodField()

    def get_image(self, obj):
        request = self.context.get('request')
        if not getattr(obj, 'image', None):
            return None
        try:
            url = obj.image.url
        except Exception:
            return None
        return _to_absolute_url(request=request, url=url)

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


class PayoutItemSerializer(serializers.ModelSerializer):
    product_name = serializers.ReadOnlyField(source='product.name')

    class Meta:
        model = PayoutItem
        fields = '__all__'


class PayoutSerializer(serializers.ModelSerializer):
    items = PayoutItemSerializer(many=True, read_only=True)
    vendor_name = serializers.ReadOnlyField()
    vendor_id = serializers.ReadOnlyField()

    class Meta:
        model = Payout
        fields = '__all__'

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


class VideoAdSerializer(serializers.ModelSerializer):
    def to_representation(self, instance):
        rep = super().to_representation(instance)
        request = self.context.get('request')
        rep['video'] = _to_absolute_url(request=request, url=rep.get('video'))
        return rep

    class Meta:
        model = VideoAd
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
        # Field presence checks with friendly messages
        if not data.get('old_password'):
            raise serializers.ValidationError({'old_password': 'Current password is required'})
        if not data.get('new_password'):
            raise serializers.ValidationError({'new_password': 'New password is required'})
        if not data.get('confirm_password'):
            raise serializers.ValidationError({'confirm_password': 'Confirm password is required'})
        # Match check with field-specific error
        if data.get('new_password') != data.get('confirm_password'):
            raise serializers.ValidationError({'confirm_password': 'New passwords do not match'})
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


class ContactSupportSerializer(serializers.Serializer):
    """Serializer for contact support requests."""
    name = serializers.CharField(max_length=255)
    email = serializers.EmailField()
    phone = serializers.CharField(max_length=20)
    message = serializers.CharField()

    def validate(self, data):
        # Basic checks and friendly messages
        if not data.get('name'):
            raise serializers.ValidationError({'name': 'Your name is required'})
        if not data.get('email'):
            raise serializers.ValidationError({'email': 'Your email is required'})
        if not data.get('phone'):
            raise serializers.ValidationError({'phone': 'Your phone number is required'})
        if not data.get('message') or len(data.get('message').strip()) < 5:
            raise serializers.ValidationError({'message': 'Please provide a brief description (min 5 characters)'})
        return data