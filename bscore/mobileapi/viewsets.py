from django.db.models import Q
from rest_framework import permissions, status, viewsets
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import Vendor
from apis.models import (
	Banner,
	Product,
	ProductCategory,
	Service,
)
from apis.serializers import (
	BannerSerializer,
	ProductCategorySerializer,
	ProductSerializer,
	ServiceSerializer,
)


class MobileHomepageAPIView(APIView):
	"""
	Mobile homepage: banners, categories, curated products.
	Public endpoint optimized for mobile clients.
	"""

	permission_classes = [permissions.AllowAny]

	def get(self, request, *args, **kwargs):
		banners = Banner.objects.filter(is_active=True).order_by('?')[:10]
		categories = ProductCategory.objects.all().order_by('-created_at')

		# Published products only; ensure vendor is allowed
		products_qs = Product.objects.filter(is_published=True)
		allowed_ids = [
			p.id
			for p in products_qs
			if p.vendor and p.vendor.has_active_subscription() and p.vendor.can_create_or_view_product()
		]
		products = Product.objects.filter(id__in=allowed_ids).order_by('?')[:10]
		best_selling_products = Product.objects.filter(id__in=allowed_ids).order_by('?')[:10]
		new_arrivals = Product.objects.filter(id__in=allowed_ids).order_by('-created_at')[:3]

		data = {
			"banners": BannerSerializer(banners, many=True).data,
			"categories": ProductCategorySerializer(categories, many=True).data,
			"products": ProductSerializer(products, many=True).data,
			"best_selling_products": ProductSerializer(best_selling_products, many=True).data,
			"new_arrivals": ProductSerializer(new_arrivals, many=True).data,
		}
		return Response(data, status=status.HTTP_200_OK)


class ProductViewSet(viewsets.ReadOnlyModelViewSet):
	"""Mobile product endpoints (list/retrieve only)."""

	serializer_class = ProductSerializer
	permission_classes = [permissions.AllowAny]

	def get_queryset(self):
		qs = Product.objects.filter(is_published=True)
		# Enforce vendor eligibility
		allowed_ids = [
			p.id
			for p in qs
			if p.vendor and p.vendor.has_active_subscription() and p.vendor.can_create_or_view_product()
		]
		qs = Product.objects.filter(id__in=allowed_ids)

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
