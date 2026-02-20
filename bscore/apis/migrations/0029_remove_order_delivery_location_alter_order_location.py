"""Unify Order location fields safely.

DB currently has both:
- Order.location (CharField)
- Order.delivery_location (FK -> Location)

We want a single FK field named `location`.

This migration avoids the SQLite pitfall where altering a CharField into a
ForeignKey causes legacy strings to be copied into `location_id`.
"""

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('apis', '0028_remove_order_delivery_location_alter_order_location'),
    ]


def forwards_fill_location_fk(apps, schema_editor):
    Order = apps.get_model('apis', 'Order')
    Location = apps.get_model('apis', 'Location')

    for order in Order.objects.filter(location__isnull=True).exclude(legacy_location__isnull=True):
        legacy = (order.legacy_location or '').strip()
        if not legacy:
            continue

        # Prefer any existing location with matching name (any category).
        location_obj = Location.objects.filter(name__iexact=legacy).first()
        if location_obj is None:
            # Legacy data doesn't have category; default to HALL.
            location_obj, _ = Location.objects.get_or_create(name=legacy, category='HALL')

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
