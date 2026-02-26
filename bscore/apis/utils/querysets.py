from django.db.models import OuterRef, Q, Subquery
from django.utils import timezone

from accounts.models import Subscription


def filter_products_for_public(products_qs):
    """Filter products to exclude vendors with expired subscriptions.

    Rules:
    - Include platform-owned products with vendor=NULL.
    - Include vendor products only if the vendor's latest subscription is active
      AND the subscription package allows product creation.

    Notes:
    - Implemented with Subquery so filtering happens in the DB.
    - Uses the latest Subscription by created_at for each vendor.
    """

    today = timezone.localdate()

    latest_sub_qs = Subscription.objects.filter(vendor_id=OuterRef('vendor_id')).order_by('-created_at')

    latest_end_date = Subquery(latest_sub_qs.values('end_date')[:1])
    latest_can_create_product = Subquery(latest_sub_qs.values('package__can_create_product')[:1])

    return (
        products_qs.annotate(
            _sub_end_date=latest_end_date,
            _sub_can_create_product=latest_can_create_product,
        )
        .filter(
            Q(vendor__isnull=True)
            | (Q(_sub_end_date__gte=today) & Q(_sub_can_create_product=True))
        )
    )


def filter_services_for_public(services_qs):
    """Filter services to exclude vendors with expired subscriptions.

    Rules:
    - Include platform-owned services with vendor=NULL.
    - Include vendor services only if the vendor's latest subscription is active
      AND the subscription package allows service creation.

    Notes:
    - Implemented with Subquery so filtering happens in the DB.
    - Uses the latest Subscription by created_at for each vendor.
    """

    today = timezone.localdate()

    latest_sub_qs = Subscription.objects.filter(vendor_id=OuterRef('vendor_id')).order_by('-created_at')

    latest_end_date = Subquery(latest_sub_qs.values('end_date')[:1])
    latest_can_create_service = Subquery(latest_sub_qs.values('package__can_create_service')[:1])

    return (
        services_qs.annotate(
            _sub_end_date=latest_end_date,
            _sub_can_create_service=latest_can_create_service,
        )
        .filter(
            Q(vendor__isnull=True)
            | (Q(_sub_end_date__gte=today) & Q(_sub_can_create_service=True))
        )
    )
