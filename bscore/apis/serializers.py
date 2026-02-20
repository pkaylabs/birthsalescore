import json
from decimal import Decimal

from django.conf import settings
from django.contrib.auth import authenticate
from django.db.models import Avg, Count
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
    avatar = serializers.ImageField(required=False, allow_null=True)

    def to_representation(self, instance):
        rep = super().to_representation(instance)
        request = self.context.get('request')
        if not getattr(instance, 'avatar', None):
            rep['avatar'] = None
            return rep
        try:
            url = instance.avatar.url
        except Exception:
            url = None
        rep['avatar'] = _to_absolute_url(request=request, url=url)
        return rep

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
    rating = serializers.SerializerMethodField()
    ratings_count = serializers.SerializerMethodField()
    customer_can_rate_product = serializers.SerializerMethodField()

    def get_rating(self, obj):
        # Prefer prefetched ratings to avoid extra queries when available.
        cache = getattr(obj, '_prefetched_objects_cache', {}) or {}
        if 'ratings' in cache:
            ratings = [r.rating for r in cache['ratings'] if getattr(r, 'rating', None) is not None]
            if not ratings:
                return None
            return round(sum(ratings) / len(ratings), 2)
        agg = obj.ratings.aggregate(avg=Avg('rating'))
        avg = agg.get('avg')
        return round(float(avg), 2) if avg is not None else None

    def get_ratings_count(self, obj):
        cache = getattr(obj, '_prefetched_objects_cache', {}) or {}
        if 'ratings' in cache:
            return len(cache['ratings'])
        agg = obj.ratings.aggregate(cnt=Count('id'))
        return int(agg.get('cnt') or 0)

    def get_customer_can_rate_product(self, obj):
        request = self.context.get('request')
        if request is None:
            return False

        user = getattr(request, 'user', None)
        if not user or not getattr(user, 'is_authenticated', False):
            return False

        # Only customers can rate.
        if getattr(user, 'user_type', None) != 'CUSTOMER':
            return False

        cache_key = '_customer_ordered_product_ids'
        product_ids = self.context.get(cache_key)
        if product_ids is None:
            product_ids = set(
                Order.objects.filter(user=user)
                .exclude(status='Cancelled')
                .values_list('items__product_id', flat=True)
                .distinct()
            )
            self.context[cache_key] = product_ids

        return obj.id in product_ids

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
    image = serializers.ImageField(required=False, allow_null=True)

    def to_representation(self, instance):
        rep = super().to_representation(instance)
        request = self.context.get('request')
        if not getattr(instance, 'image', None):
            rep['image'] = None
            return rep
        try:
            url = instance.image.url
        except Exception:
            url = None
        rep['image'] = _to_absolute_url(request=request, url=url)
        return rep

    class Meta:
        model = ProductImages
        fields = '__all__'
        extra_kwargs = {
            'product': {'required': False},
        }

class ProductReviewSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductReview
        fields = '__all__'


class ProductRatingSerializer(serializers.ModelSerializer):
    user_name = serializers.ReadOnlyField(source='user.name')

    class Meta:
        model = ProductRating
        fields = '__all__'
        read_only_fields = ('user', 'created_at', 'updated_at')

class OrderItemSerializer(serializers.ModelSerializer):
    product_name = serializers.ReadOnlyField()
    class Meta:
        model = OrderItem
        fields = '__all__'

class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)
    payment_status = serializers.ReadOnlyField()
    total_price = serializers.ReadOnlyField()
    total_amount = serializers.ReadOnlyField()
    location_name = serializers.ReadOnlyField(source='location.name')
    location_category = serializers.ReadOnlyField(source='location.category')
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
    # Accept flexible input (Location id or name), then resolve to Location FK.
    location = serializers.CharField()
    
    class Meta:
        model = Order
        fields = ['user', 'items', 'status', 'location', 'customer_phone']

    def validate(self, attrs):
        attrs = super().validate(attrs)
        location_input = attrs.get('location')
        if not location_input:
            raise serializers.ValidationError({"location": "location is required"})

        items = attrs.get('items') or []

        errors = []
        for idx, item in enumerate(items):
            product = item.get('product')
            if not product:
                errors.append({"index": idx, "detail": "product is required"})
                continue

            chosen_color = item.get('color')
            chosen_size = item.get('size')

            if chosen_color:
                available = getattr(product, 'available_colors', None) or []
                if available:
                    available_lower = {str(c).strip().lower() for c in available if str(c).strip()}
                    if str(chosen_color).strip().lower() not in available_lower:
                        errors.append({
                            "index": idx,
                            "field": "color",
                            "detail": "Invalid color for product",
                            "allowed": available,
                        })

            if chosen_size:
                available = getattr(product, 'available_sizes', None) or []
                if available:
                    available_lower = {str(s).strip().lower() for s in available if str(s).strip()}
                    if str(chosen_size).strip().lower() not in available_lower:
                        errors.append({
                            "index": idx,
                            "field": "size",
                            "detail": "Invalid size for product",
                            "allowed": available,
                        })

        if errors:
            raise serializers.ValidationError({"items": errors})

        # Resolve delivery location and fee.
        location_obj = None
        if isinstance(location_input, int) or (isinstance(location_input, str) and location_input.isdigit()):
            location_obj = Location.objects.filter(id=int(location_input)).first()
        else:
            location_obj = Location.objects.filter(name__iexact=str(location_input).strip()).first()

        if not location_obj:
            raise serializers.ValidationError({"location": "Invalid location"})

        fee = DeliveryFee.objects.filter(location=location_obj).first()
        delivery_fee_amount = fee.price if fee else Decimal('0.00')

        # Store resolved objects for create().
        self.context['_location_obj'] = location_obj
        self.context['_delivery_fee_amount'] = delivery_fee_amount

        # Store FK instance on the model field.
        attrs['location'] = location_obj
        return attrs
    
    def create(self, validated_data):
        items_data = validated_data.pop('items')
        delivery_fee_amount = self.context.get('_delivery_fee_amount')
        if delivery_fee_amount in (None, ""):
            delivery_fee_amount = Decimal('0.00')
        order = Order.objects.create(
            **validated_data,
            delivery_fee_amount=delivery_fee_amount,
        )
        order_items = []
        for item_data in items_data:
            product = item_data['product']
            quantity = item_data.get('quantity', 1)
            color = item_data.get('color')
            size = item_data.get('size')
            order_item = OrderItem.objects.create(
                product=product,
                quantity=quantity,
                color=color,
                size=size,
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


class LocationSerializer(serializers.ModelSerializer):
    delivery_fee_price = serializers.SerializerMethodField()

    def get_delivery_fee_price(self, obj):
        fee = getattr(obj, 'delivery_fee', None)
        price = getattr(fee, 'price', None)
        if price is None:
            return 0.0
        try:
            return float(price)
        except Exception:
            return 0.0

    class Meta:
        model = Location
        fields = (
            'id',
            'name',
            'category',
            'delivery_fee_price',
            'created_at',
            'updated_at',
        )
        read_only_fields = ('created_at', 'updated_at', 'delivery_fee_price')


class DeliveryFeeSerializer(serializers.ModelSerializer):
    location_name = serializers.ReadOnlyField(source='location.name')
    location_category = serializers.ReadOnlyField(source='location.category')

    class Meta:
        model = DeliveryFee
        fields = (
            'id',
            'location',
            'location_name',
            'location_category',
            'price',
            'created_at',
            'updated_at',
        )
        read_only_fields = ('created_at', 'updated_at', 'location_name', 'location_category')


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