"""Unify Order location fields.

Historically Order had:
- `location` (CharField)
- `delivery_location` (FK -> Location)

We unify these into a single FK field named `location`.

This migration:
1) Renames legacy text `location` to `legacy_location`.
2) Renames FK `delivery_location` to `location`.
3) Backfills FK `location` from legacy text where needed.
4) Drops `legacy_location`.
"""

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('apis', '0027_order_delivery_fee_amount_location_deliveryfee_and_more'),
    ]


def forwards_fill_location_fk(apps, schema_editor):
    Order = apps.get_model('apis', 'Order')
    Location = apps.get_model('apis', 'Location')

    # Only fill FK for orders where FK is missing.
    for order in Order.objects.filter(location__isnull=True).exclude(legacy_location__isnull=True):
        legacy = (order.legacy_location or '').strip()
        if not legacy:
            continue

        # Prefer any existing location with matching name (any category).
        location_obj = Location.objects.filter(name__iexact=legacy).first()
        if location_obj is None:
            # Legacy data doesn't have category; default to HALL.
            location_obj, _ = Location.objects.get_or_create(
                name=legacy,
                category='HALL',
            )

        order.location = location_obj
        order.save(update_fields=['location'])

    operations = [
        migrations.RenameField(
            model_name='order',
            old_name='location',
            new_name='legacy_location',
        ),
        migrations.RenameField(
            model_name='order',
            old_name='delivery_location',
            new_name='location',
        ),
        migrations.RunPython(forwards_fill_location_fk, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name='order',
            name='legacy_location',
        ),
    ]
