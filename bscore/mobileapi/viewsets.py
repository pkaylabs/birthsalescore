from django.conf import settings
from django.utils import timezone
from django.db.models import Q
from rest_framework import permissions, status, viewsets
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema, OpenApiExample, OpenApiResponse

from apis.models import (
	Banner,
	ServiceBooking,
	UserVideoAdState,
	Product,
	ProductCategory,
	Service,
	VideoAd,
)
from apis.utils.querysets import filter_products_for_public
from apis.serializers import (
	BannerSerializer,
	ProductCategorySerializer,
	ProductSerializer,
	ServiceSerializer,
)

from .serializers import MobileServiceBookingCreateSerializer, MobileServiceBookingSerializer


class MobileHomepageAPIView(APIView):
	"""
	Mobile homepage: banners, categories, curated products.
	Public endpoint optimized for mobile clients.
	"""

	permission_classes = [permissions.AllowAny]

	def get(self, request, *args, **kwargs):
		video_ad_url = None
		if request.user.is_authenticated:
			interval = getattr(settings, 'VIDEO_AD_INTERVAL_SECONDS', 60)
			state, _ = UserVideoAdState.objects.get_or_create(user=request.user)
			now = timezone.now()

			if state.last_shown_at is None or (now - state.last_shown_at).total_seconds() >= interval:
				ad = VideoAd.objects.filter(is_active=True).order_by('?').first()
				if ad:
					try:
						url = ad.video.url
					except Exception:
						url = None
					if url:
						video_ad_url = request.build_absolute_uri(url)
						state.last_shown_at = now
						state.save(update_fields=['last_shown_at', 'updated_at'])
		# Featured content: use active banners as featured slots
		featured = Banner.objects.filter(is_active=True).order_by('-created_at')[:10]
		categories = ProductCategory.objects.all().order_by('-created_at')

		# Published products only; ensure vendor is allowed
		products_top = filter_products_for_public(Product.objects.filter(is_published=True)).order_by('-created_at')[:50]

		data = {
			"categories": ProductCategorySerializer(categories, many=True).data,
			"featured": BannerSerializer(featured, many=True, context={"request": request}).data,
			"products": ProductSerializer(products_top, many=True, context={"request": request}).data,
			"video_ad_url": video_ad_url,
		}
		return Response(data, status=status.HTTP_200_OK)


class ProductViewSet(viewsets.ReadOnlyModelViewSet):
	"""Mobile product endpoints (list/retrieve only)."""

	serializer_class = ProductSerializer
	permission_classes = [permissions.AllowAny]

	def get_queryset(self):
		qs = filter_products_for_public(Product.objects.filter(is_published=True))

		# Optional filtering
		category_id = self.request.query_params.get('category_id')
		query = self.request.query_params.get('q')
		if category_id and category_id.isdigit():
			qs = qs.filter(category_id=category_id)
		if query:
			qs = qs.filter(
				Q(name__icontains=query) | Q(description__icontains=query) | Q(category__name__icontains=query)
			)
		return qs.order_by('-created_at')


class ServiceViewSet(viewsets.ReadOnlyModelViewSet):
	"""Mobile service endpoints (list/retrieve only)."""

	serializer_class = ServiceSerializer
	permission_classes = [permissions.AllowAny]

	def get_queryset(self):
		qs = Service.objects.filter(published=True)
		allowed_ids = [
			s.id
			for s in qs
			if s.vendor and s.vendor.has_active_subscription() and s.vendor.can_create_or_view_service()
		]
		qs = Service.objects.filter(id__in=allowed_ids)
		query = self.request.query_params.get('q')
		if query:
			qs = qs.filter(Q(name__icontains=query) | Q(description__icontains=query))
		return qs.order_by('-created_at')


class CategoryViewSet(viewsets.ReadOnlyModelViewSet):
	"""Mobile product categories (list/retrieve)."""

	serializer_class = ProductCategorySerializer
	permission_classes = [permissions.AllowAny]

	def get_queryset(self):
		return ProductCategory.objects.all().order_by('-created_at')


class BannerViewSet(viewsets.ReadOnlyModelViewSet):
	"""Mobile banners (active only)."""

	serializer_class = BannerSerializer
	permission_classes = [permissions.AllowAny]

	def get_queryset(self):
		return Banner.objects.filter(is_active=True).order_by('-created_at')


class MobileMyBookingsAPIView(APIView):
	"""List bookings belonging to the authenticated mobile user/customer."""

	permission_classes = (permissions.IsAuthenticated,)
	serializer_class = MobileServiceBookingSerializer

	@extend_schema(
		summary='List my service bookings',
		description='Returns the authenticated user/customer\'s service bookings (newest first).',
		responses={
			200: OpenApiResponse(
				response=MobileServiceBookingSerializer(many=True),
				description='List of bookings',
				examples=[
					OpenApiExample(
						'Bookings Response',
						value=[
							{
								"id": 12,
								"service": 3,
								"service_name": "Home Cleaning",
								"service_price": 150.00,
								"date": "2026-03-31",
								"time": "14:00:00",
								"location": "Hall A",
								"other_location": None,
								"status": "Pending",
								"payment_status": "Pending",
								"vendor_name": "Sparkle Services",
								"vendor_phone": "+233501234567",
								"created_at": "2026-03-31T10:00:00Z",
								"updated_at": "2026-03-31T10:00:00Z"
							}
						],
					)
				],
			),
			401: OpenApiResponse(description='Authentication required'),
		},
		tags=['Mobile - Bookings'],
	)
	def get(self, request, *args, **kwargs):
		bookings = (
			ServiceBooking.objects.filter(user=request.user)
			.select_related('service', 'service__vendor')
			.order_by('-created_at')
		)
		serializer = MobileServiceBookingSerializer(bookings, many=True, context={"request": request})
		return Response(serializer.data, status=status.HTTP_200_OK)

	@extend_schema(
		summary='Create a service booking',
		description=(
			'Creates a new service booking for the authenticated user/customer. '
			'The service must be published and the vendor must have an active subscription.'
		),
		request=MobileServiceBookingCreateSerializer,
		responses={
			201: OpenApiResponse(
				response=MobileServiceBookingSerializer,
				description='Booking created',
				examples=[
					OpenApiExample(
						'Create Booking Response',
						value={
							"id": 12,
							"service": 3,
							"service_name": "Home Cleaning",
							"service_price": 150.00,
							"date": "2026-03-31",
							"time": "14:00:00",
							"location": "Hall A",
							"other_location": None,
							"status": "Pending",
							"payment_status": "None",
							"vendor_name": "Sparkle Services",
							"vendor_phone": "+233501234567",
							"created_at": "2026-03-31T10:00:00Z",
							"updated_at": "2026-03-31T10:00:00Z",
						},
						response_only=True,
					)
				],
			),
			400: OpenApiResponse(description='Invalid request body'),
			401: OpenApiResponse(description='Authentication required'),
		},
		examples=[
			OpenApiExample(
				'Create Booking Request',
				value={
					"service": 3,
					"date": "2026-03-31",
					"time": "14:00:00",
					"location": "Other",
					"other_location": "Near the main gate",
				},
				request_only=True,
			)
		],
		tags=['Mobile - Bookings'],
	)
	def post(self, request, *args, **kwargs):
		serializer = MobileServiceBookingCreateSerializer(data=request.data, context={"request": request})
		serializer.is_valid(raise_exception=True)
		booking = serializer.save(user=request.user)

		response_serializer = MobileServiceBookingSerializer(booking, context={"request": request})
		return Response(response_serializer.data, status=status.HTTP_201_CREATED)
