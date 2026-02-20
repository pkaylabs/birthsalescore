"""Unify Order location fields safely.

IMPORTANT: Previous migrations 0028/0029 in this repo ended up as no-ops in some
environments (missing `operations` on the Migration class). This migration is
the real fix.

Historically Order had:
- `location` (CharField)
- `delivery_location` (FK -> Location)

We unify these into a single FK field named `location`.

We avoid altering a CharField into a FK directly because SQLite will copy legacy
strings (e.g. "L.U") into `location_id`, causing FK integrity failures.
"""

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('apis', '0029_remove_order_delivery_location_alter_order_location'),
    ]


def forwards_fill_location_fk(apps, schema_editor):
    Order = apps.get_model('apis', 'Order')
    Location = apps.get_model('apis', 'Location')

    # Only fill FK for orders where FK is missing.
    for order in Order.objects.filter(location__isnull=True).exclude(legacy_location__isnull=True):
        legacy = (order.legacy_location or '').strip()
        if not legacy:
            continue

        location_obj = Location.objects.filter(name__iexact=legacy).first()
        if location_obj is None:
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
