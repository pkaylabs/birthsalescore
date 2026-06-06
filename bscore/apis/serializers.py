import json
from decimal import Decimal, ROUND_HALF_UP

from django.conf import settings
from django.contrib.auth import authenticate
from django.db import transaction
from django.db.models import Avg, Count
from rest_framework import serializers

from accounts.models import *
from apis.models import *
from apis.utils.querysets import filter_products_for_public


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
    low_stock = serializers.ReadOnlyField()

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
        if 'stock_quantity' in attrs:
            attrs['in_stock'] = attrs.get('stock_quantity', 0) > 0
        elif 'in_stock' in attrs:
            if attrs.get('in_stock'):
                current = getattr(self.instance, 'stock_quantity', 0) if self.instance else 0
                attrs['stock_quantity'] = max(current, 1)
            else:
                attrs['stock_quantity'] = 0
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


class ServiceImagesSerializer(serializers.ModelSerializer):
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
        model = ServiceImages
        fields = '__all__'
        extra_kwargs = {
            'service': {'required': False},
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


class VendorPublishingCreditCouponSerializer(serializers.ModelSerializer):
    times_redeemed = serializers.ReadOnlyField()
    expired = serializers.ReadOnlyField()
    redeemable = serializers.ReadOnlyField()

    class Meta:
        model = VendorPublishingCreditCoupon
        fields = '__all__'
        read_only_fields = ('created_by', 'created_at', 'updated_at')

    def validate_code(self, value):
        return str(value).strip().upper()

    def validate(self, attrs):
        attrs = super().validate(attrs)
        credit_type = attrs.get('credit_type', getattr(self.instance, 'credit_type', 'BOTH'))
        product_credits = attrs.get('product_credits', getattr(self.instance, 'product_credits', 0))
        service_credits = attrs.get('service_credits', getattr(self.instance, 'service_credits', 0))
        if credit_type in ('PRODUCT', 'BOTH') and product_credits <= 0 and credit_type != 'SERVICE':
            raise serializers.ValidationError({"product_credits": "Product credits must be greater than zero"})
        if credit_type in ('SERVICE', 'BOTH') and service_credits <= 0 and credit_type != 'PRODUCT':
            raise serializers.ValidationError({"service_credits": "Service credits must be greater than zero"})
        return attrs


class VendorPublishingCreditRedemptionSerializer(serializers.ModelSerializer):
    coupon_code = serializers.ReadOnlyField(source='coupon.code')
    vendor_name = serializers.ReadOnlyField(source='vendor.vendor_name')

    class Meta:
        model = VendorPublishingCreditRedemption
        fields = '__all__'
        read_only_fields = ('vendor', 'coupon', 'product_credits', 'service_credits', 'redeemed_at')


class VendorCustomerCouponSerializer(serializers.ModelSerializer):
    times_redeemed = serializers.ReadOnlyField()
    expired = serializers.ReadOnlyField()
    redeemable = serializers.ReadOnlyField()
    vendor_name = serializers.ReadOnlyField()

    class Meta:
        model = VendorCustomerCoupon
        fields = '__all__'
        read_only_fields = ('vendor', 'created_at', 'updated_at')

    def validate_code(self, value):
        return str(value).strip().upper()

    def validate(self, attrs):
        attrs = super().validate(attrs)
        discount_type = attrs.get('discount_type', getattr(self.instance, 'discount_type', 'PERCENTAGE'))
        discount_value = Decimal(attrs.get('discount_value', getattr(self.instance, 'discount_value', 0)))
        if discount_value <= 0:
            raise serializers.ValidationError({"discount_value": "Discount value must be greater than zero"})
        if discount_type == 'PERCENTAGE' and discount_value > 100:
            raise serializers.ValidationError({"discount_value": "Percentage discount cannot exceed 100"})
        return attrs


class OrderItemSerializer(serializers.ModelSerializer):
    product = serializers.PrimaryKeyRelatedField(queryset=Product.objects.filter(is_deleted=False))
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
    other_location = serializers.CharField(required=False, allow_null=True)
    coupon_code = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    class Meta:
        model = Order
        fields = ['user', 'items', 'status', 'location', 'other_location', 'customer_phone', 'coupon_code']

    def validate(self, attrs):
        attrs = super().validate(attrs)
        location_input = attrs.get('location')
        if not location_input:
            raise serializers.ValidationError({"location": "location is required"})

        items = attrs.get('items') or []

        errors = []
        requested_quantities = {}
        for idx, item in enumerate(items):
            product = item.get('product')
            if not product:
                errors.append({"index": idx, "detail": "product is required"})
                continue

            quantity = item.get('quantity', 1) or 1
            try:
                quantity = int(quantity)
            except (TypeError, ValueError):
                errors.append({"index": idx, "field": "quantity", "detail": "Quantity must be a whole number"})
                continue
            if quantity <= 0:
                errors.append({"index": idx, "field": "quantity", "detail": "Quantity must be greater than zero"})
                continue
            item['quantity'] = quantity
            requested_quantities[product.id] = requested_quantities.get(product.id, 0) + quantity

            # Block soft-deleted products.
            if getattr(product, 'is_deleted', False):
                errors.append({"index": idx, "field": "product", "detail": "Product is not available"})
                continue

            # Block unpublished or subscription-ineligible vendor products.
            allowed = filter_products_for_public(
                Product.objects.filter(id=product.id, is_published=True, is_deleted=False)
            ).exists()
            if not allowed:
                errors.append({"index": idx, "field": "product", "detail": "Product is not available"})
                continue

            if not getattr(product, 'in_stock', False) or getattr(product, 'stock_quantity', 0) <= 0:
                errors.append({"index": idx, "field": "product", "detail": "Product is out of stock"})
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

        for idx, item in enumerate(items):
            product = item.get('product')
            if not product:
                continue
            requested = requested_quantities.get(product.id, 0)
            available = getattr(product, 'stock_quantity', 0)
            if requested > available:
                errors.append({
                    "index": idx,
                    "field": "quantity",
                    "detail": f"Only {available} unit(s) available for this product",
                    "available": available,
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

        coupon = None
        discount_amount = Decimal('0.00')
        coupon_code = (attrs.get('coupon_code') or '').strip().upper()
        if coupon_code:
            user = attrs.get('user')
            coupon = VendorCustomerCoupon.objects.select_related('vendor').filter(code=coupon_code).first()
            if not coupon:
                raise serializers.ValidationError({"coupon_code": "Coupon not found"})
            if not coupon.redeemable:
                raise serializers.ValidationError({"coupon_code": "Coupon is expired, inactive, or fully redeemed"})
            if user and VendorCustomerCouponRedemption.objects.filter(
                coupon=coupon,
                customer=user,
            ).count() >= coupon.per_customer_limit:
                raise serializers.ValidationError({"coupon_code": "You have already used this coupon"})

            eligible_subtotal = Decimal('0.00')
            for item in items:
                product = item.get('product')
                if product and getattr(product, 'vendor_id', None) == coupon.vendor_id:
                    eligible_subtotal += Decimal(product.price) * Decimal(item.get('quantity', 1) or 1)

            if eligible_subtotal <= 0:
                raise serializers.ValidationError({"coupon_code": "Coupon is not valid for these products"})
            if eligible_subtotal < Decimal(coupon.minimum_order_amount):
                raise serializers.ValidationError({
                    "coupon_code": f"Minimum eligible order amount is {coupon.minimum_order_amount}"
                })

            if coupon.discount_type == 'PERCENTAGE':
                discount_amount = (eligible_subtotal * Decimal(coupon.discount_value) / Decimal('100')).quantize(
                    Decimal('0.01'), rounding=ROUND_HALF_UP
                )
            else:
                discount_amount = min(Decimal(coupon.discount_value), eligible_subtotal)

        # Store resolved objects for create().
        self.context['_location_obj'] = location_obj
        self.context['_delivery_fee_amount'] = delivery_fee_amount
        self.context['_applied_coupon'] = coupon
        self.context['_discount_amount'] = discount_amount

        # Store FK instance on the model field.
        attrs['location'] = location_obj
        attrs['coupon_code'] = coupon_code or None
        return attrs
    
    def create(self, validated_data):
        items_data = validated_data.pop('items')
        delivery_fee_amount = self.context.get('_delivery_fee_amount')
        if delivery_fee_amount in (None, ""):
            delivery_fee_amount = Decimal('0.00')
        applied_coupon = self.context.get('_applied_coupon')
        discount_amount = self.context.get('_discount_amount') or Decimal('0.00')

        # Compute service fee from active ServiceFee config.
        items_subtotal = Decimal('0.00')
        for item_data in items_data:
            product = item_data['product']
            quantity = item_data.get('quantity', 1) or 1
            try:
                items_subtotal += (Decimal(product.price) * Decimal(quantity))
            except Exception:
                # If anything goes wrong, fall back to 0 for safety.
                items_subtotal += Decimal('0.00')

        service_fee_amount = Decimal('0.00')
        try:
            active_fee = ServiceFee.objects.filter(is_active=True).order_by('-created_at').first()
            if active_fee and active_fee.value is not None:
                if active_fee.fee_type == 'FLAT':
                    service_fee_amount = Decimal(active_fee.value)
                else:
                    # Percentage applied to items subtotal (not including delivery fee).
                    service_fee_amount = (items_subtotal * Decimal(active_fee.value) / Decimal('100')).quantize(
                        Decimal('0.01'), rounding=ROUND_HALF_UP
                    )
        except Exception:
            service_fee_amount = Decimal('0.00')

        with transaction.atomic():
            if applied_coupon:
                applied_coupon = VendorCustomerCoupon.objects.select_for_update().filter(id=applied_coupon.id).first()
                if not applied_coupon or not applied_coupon.redeemable:
                    raise serializers.ValidationError({"coupon_code": "Coupon is expired, inactive, or fully redeemed"})
                if VendorCustomerCouponRedemption.objects.filter(
                    coupon=applied_coupon,
                    customer=validated_data.get('user'),
                ).count() >= applied_coupon.per_customer_limit:
                    raise serializers.ValidationError({"coupon_code": "You have already used this coupon"})

            product_ids = [item_data['product'].id for item_data in items_data]
            locked_products = {
                product.id: product
                for product in Product.objects.select_for_update().filter(id__in=product_ids)
            }
            requested_quantities = {}
            for item_data in items_data:
                product_id = item_data['product'].id
                quantity = item_data.get('quantity', 1) or 1
                requested_quantities[product_id] = requested_quantities.get(product_id, 0) + quantity

            stock_errors = []
            for product_id, quantity in requested_quantities.items():
                product = locked_products.get(product_id)
                available = getattr(product, 'stock_quantity', 0) if product else 0
                if not product or available < quantity:
                    stock_errors.append({
                        "product": product_id,
                        "detail": f"Only {available} unit(s) available for this product",
                        "available": available,
                    })
            if stock_errors:
                raise serializers.ValidationError({"items": stock_errors})

            order = Order.objects.create(
                **validated_data,
                delivery_fee_amount=delivery_fee_amount,
                service_fee_amount=service_fee_amount,
                applied_coupon=applied_coupon,
                discount_amount=discount_amount,
            )
            order_items = []
            for item_data in items_data:
                product = locked_products[item_data['product'].id]
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

            order.items.set(order_items)

            for product_id, quantity in requested_quantities.items():
                product = locked_products[product_id]
                product.stock_quantity -= quantity
                product.save(update_fields=['stock_quantity', 'in_stock', 'updated_at'])

            if applied_coupon and discount_amount > 0:
                VendorCustomerCouponRedemption.objects.create(
                    coupon=applied_coupon,
                    order=order,
                    customer=order.user,
                    discount_amount=discount_amount,
                )

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
    images = serializers.SerializerMethodField()

    def get_bookings(self, obj):
        bookings = ServiceBooking.objects.filter(service=obj).count()
        return bookings

    def get_images(self, obj):
        images_qs = getattr(obj, 'images', None)
        if images_qs is None:
            return []
        serializer = ServiceImagesSerializer(images_qs.all(), many=True, context=self.context)
        return serializer.data

    def to_representation(self, instance):
        rep = super().to_representation(instance)
        request = self.context.get('request')
        rep['image'] = _to_absolute_url(request=request, url=rep.get('image'))
        return rep
    
    class Meta:
        model = Service
        fields = '__all__'

class AdSerializer(serializers.ModelSerializer):
    class Meta:
        model = Ad
        fields = '__all__'

class BannerSerializer(serializers.ModelSerializer):

    def to_representation(self, instance):
        rep = super().to_representation(instance)
        request = self.context.get('request')
        rep['image'] = _to_absolute_url(request=request, url=rep.get('image'))
        return rep

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


class ServiceFeeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ServiceFee
        fields = (
            'id',
            'fee_type',
            'value',
            'is_active',
            'created_at',
            'updated_at',
        )
        read_only_fields = ('created_at', 'updated_at')

    def validate(self, attrs):
        attrs = super().validate(attrs)
        fee_type = attrs.get('fee_type') or getattr(self.instance, 'fee_type', None)
        value = attrs.get('value') if 'value' in attrs else getattr(self.instance, 'value', None)

        if fee_type == 'PERCENTAGE' and value is not None:
            try:
                if value < 0 or value > 100:
                    raise serializers.ValidationError({'value': 'Percentage fee must be between 0 and 100'})
            except TypeError:
                raise serializers.ValidationError({'value': 'Invalid value'})

        if fee_type == 'FLAT' and value is not None:
            try:
                if value < 0:
                    raise serializers.ValidationError({'value': 'Flat fee must be >= 0'})
            except TypeError:
                raise serializers.ValidationError({'value': 'Invalid value'})

        return attrs


class ActiveServiceFeeResponseSerializer(serializers.Serializer):
    service_fee = ServiceFeeSerializer(required=False, allow_null=True)
    computed_fee_amount = serializers.CharField()
    computed_on_amount = serializers.CharField(required=False)


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

    vendor_name = serializers.SerializerMethodField()

    def get_vendor_name(self, obj):
        # Preferred: direct vendor on payment (subscription/booking/single-vendor flows).
        vendor = getattr(obj, 'vendor', None)
        if vendor and getattr(vendor, 'vendor_name', None):
            return vendor.vendor_name

        # For multi-vendor order payments, payment.vendor may be null.
        order = getattr(obj, 'order', None)
        if order:
            names = set()
            try:
                items = order.items.select_related('product', 'product__vendor').all()
            except Exception:
                items = order.items.all()
            for item in items:
                product = getattr(item, 'product', None)
                if not product:
                    continue
                product_vendor = getattr(product, 'vendor', None)
                if product_vendor and getattr(product_vendor, 'vendor_name', None):
                    names.add(product_vendor.vendor_name)
                else:
                    # Platform-owned products (vendor is null)
                    fallback = getattr(product, 'vendor_name', None)
                    if fallback:
                        names.add(str(fallback))
            if len(names) == 1:
                return next(iter(names))
            if len(names) > 1:
                return 'Multiple Vendors'

        # Fallback
        return None

    class Meta:
        model = Payment
        fields = '__all__'


class MakePaystackPaymentRequestSerializer(serializers.Serializer):
    """Request body for initializing a Paystack payment."""

    subscription = serializers.IntegerField(required=False, min_value=1)
    order = serializers.IntegerField(required=False, min_value=1)
    booking = serializers.IntegerField(required=False, min_value=1)

    # Optional overrides; email is required only if user.email is not set.
    email = serializers.EmailField(required=False, allow_blank=True)
    callback_url = serializers.URLField(required=False, allow_blank=True)

    def validate(self, attrs):
        attrs = super().validate(attrs)
        provided = [k for k in ['subscription', 'order', 'booking'] if attrs.get(k) is not None]
        if len(provided) != 1:
            raise serializers.ValidationError(
                'Exactly one of subscription, order, or booking is required.'
            )
        return attrs


class MakePaystackPaymentResponseSerializer(serializers.Serializer):
    """Response body for Paystack initialization."""

    status = serializers.CharField()
    message = serializers.CharField(required=False, allow_blank=True)
    authorization_url = serializers.URLField(required=False, allow_blank=True)
    reference = serializers.CharField(required=False, allow_blank=True)
    transaction = PaymentSerializer(required=False)
    api_status = serializers.IntegerField(required=False)


class RefundSerializer(serializers.ModelSerializer):
    class Meta:
        model = Refund
        fields = '__all__'


class RefundInitiateSerializer(serializers.Serializer):
    """Request serializer for initiating/reconciling a refund."""

    payment_id = serializers.CharField()
    phone = serializers.CharField(required=False, allow_blank=False)
    provider_code = serializers.CharField(required=False, allow_blank=False)

    recipient_type = serializers.CharField(required=False, default='mobile_money')
    currency = serializers.CharField(required=False, default='GHS')
    name = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    reason = serializers.CharField(required=False, allow_blank=True, allow_null=True)

    # For OTP finalization flows (optional)
    transfer_code = serializers.CharField(required=False, allow_blank=False)
    otp = serializers.CharField(required=False, allow_blank=False)


class RefundDetailSerializer(serializers.ModelSerializer):
    payment = PaymentSerializer(read_only=True)
    refunded_by_email = serializers.SerializerMethodField()
    refunded_by_name = serializers.SerializerMethodField()

    def get_refunded_by_email(self, obj):
        u = getattr(obj, 'refunded_by', None)
        return getattr(u, 'email', None) if u else None

    def get_refunded_by_name(self, obj):
        u = getattr(obj, 'refunded_by', None)
        return getattr(u, 'name', None) if u else None

    class Meta:
        model = Refund
        fields = [
            'id',
            'reference',
            'payment',
            'refunded_by',
            'refunded_by_email',
            'refunded_by_name',
            'recipient_type',
            'phone',
            'provider_code',
            'currency',
            'name',
            'amount',
            'reason',
            'recipient_code',
            'transfer_code',
            'status',
            'status_code',
            'provider_response',
            'created_at',
            'updated_at',
        ]


class RefundListSerializer(serializers.ModelSerializer):
    payment_id = serializers.SerializerMethodField()
    refunded_date = serializers.SerializerMethodField()
    refunded_by_name = serializers.SerializerMethodField()

    def get_payment_id(self, obj):
        p = getattr(obj, 'payment', None)
        return getattr(p, 'payment_id', None) if p else None

    def get_refunded_date(self, obj):
        p = getattr(obj, 'payment', None)
        return getattr(p, 'refunded_date', None) if p else None

    def get_refunded_by_name(self, obj):
        u = getattr(obj, 'refunded_by', None)
        return getattr(u, 'name', None) if u else None

    class Meta:
        model = Refund
        fields = [
            'id',
            'reference',
            'payment_id',
            'amount',
            'phone',
            'provider_code',
            'currency',
            'status',
            'status_code',
            'refunded_by_name',
            'refunded_date',
            'created_at',
        ]

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
