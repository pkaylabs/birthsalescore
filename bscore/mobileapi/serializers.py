from rest_framework import serializers

from apis.models import ServiceBooking


class MobilePhoneSerializer(serializers.Serializer):
	phone = serializers.CharField()


class MobilePhoneOTPSerializer(serializers.Serializer):
	phone = serializers.CharField()
	otp = serializers.CharField()


class MobileForgotPasswordResetSerializer(serializers.Serializer):
	phone = serializers.CharField()
	otp = serializers.CharField()
	new_password = serializers.CharField()
	confirm_password = serializers.CharField()

	def validate(self, data):
		data = super().validate(data)
		if not data.get('new_password'):
			raise serializers.ValidationError({'new_password': 'New password is required'})
		if not data.get('confirm_password'):
			raise serializers.ValidationError({'confirm_password': 'Confirm password is required'})
		if data.get('new_password') != data.get('confirm_password'):
			raise serializers.ValidationError({'confirm_password': 'New passwords do not match'})
		return data


class MobileServiceBookingSerializer(serializers.ModelSerializer):
	"""Lightweight booking representation for mobile customers."""

	service_name = serializers.ReadOnlyField()
	vendor_name = serializers.SerializerMethodField()
	vendor_phone = serializers.SerializerMethodField()
	service_price = serializers.SerializerMethodField()
	payment_status = serializers.ReadOnlyField()

	def get_service_price(self, obj) -> float | None:
		service = getattr(obj, 'service', None)
		return getattr(service, 'price', None) if service else None

	def get_vendor_name(self, obj) -> str | None:
		vendor = getattr(getattr(obj, 'service', None), 'vendor', None)
		return getattr(vendor, 'vendor_name', None)

	def get_vendor_phone(self, obj) -> str | None:
		vendor = getattr(getattr(obj, 'service', None), 'vendor', None)
		return getattr(vendor, 'vendor_phone', None)

	class Meta:
		model = ServiceBooking
		fields = [
			'id',
			'service',
			'service_name',
			'service_price',
			'date',
			'time',
			'location',
			'other_location',
			'status',
			'payment_status',
			'vendor_name',
			'vendor_phone',
			'created_at',
			'updated_at',
		]


class MobileServiceBookingCreateSerializer(serializers.ModelSerializer):
	"""Create a service booking for the authenticated mobile user/customer."""

	class Meta:
		model = ServiceBooking
		fields = [
			'service',
			'date',
			'time',
			'location',
			'other_location',
		]

	def validate_service(self, service):
		if not getattr(service, 'published', False):
			raise serializers.ValidationError('Service is not available for booking.')

		vendor = getattr(service, 'vendor', None)
		if vendor is None:
			raise serializers.ValidationError('Service vendor is not available.')
		if not vendor.has_active_subscription():
			raise serializers.ValidationError('Service provider subscription is not active.')
		if not vendor.can_create_or_view_service():
			raise serializers.ValidationError('Service provider is not allowed to offer services.')

		return service

	def validate(self, data):
		data = super().validate(data)
		location = data.get('location')
		other_location = data.get('other_location')
		if location and location.strip().lower() == 'other':
			if not other_location or not other_location.strip():
				raise serializers.ValidationError(
					{'other_location': "This field is required when location is 'Other'."}
				)
		return data
