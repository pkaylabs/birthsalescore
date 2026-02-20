"""Database-only fix for Order.location schema drift.

In some environments, prior migrations that were meant to unify Order location
fields were marked as applied but performed no DB operations (mis-indented
`operations`). That leaves the database with legacy columns:

- apis_order.location (text)
- apis_order.delivery_location_id (FK)

…and missing the column required by the current model state:

- apis_order.location_id (FK)

This migration brings the database in line with the current Django model state
AND repairs the migration state using SeparateDatabaseAndState.
"""

import django.db.models.deletion
from django.db import migrations, models


def forwards_fix_order_location_db(apps, schema_editor):
    Location = apps.get_model('apis', 'Location')

    table = 'apis_order'

    qn = schema_editor.quote_name

    with schema_editor.connection.cursor() as cursor:
        existing_columns = {col.name for col in schema_editor.connection.introspection.get_table_description(cursor, table)}

    # Ensure `location_id` exists (current model expects it).
    if 'location_id' not in existing_columns:
        with schema_editor.connection.cursor() as cursor:
            cursor.execute(f"ALTER TABLE {qn(table)} ADD COLUMN {qn('location_id')} bigint NULL")

    # Refresh column list after adding.
    with schema_editor.connection.cursor() as cursor:
        existing_columns = {col.name for col in schema_editor.connection.introspection.get_table_description(cursor, table)}

    # First, if legacy FK column exists, copy it into the new column.
    if 'delivery_location_id' in existing_columns:
        with schema_editor.connection.cursor() as cursor:
            cursor.execute(
                f"UPDATE {qn(table)} "
                f"SET {qn('location_id')} = {qn('delivery_location_id')} "
                f"WHERE {qn('location_id')} IS NULL AND {qn('delivery_location_id')} IS NOT NULL"
            )

    # Then, if legacy text column exists, create/find Location and backfill.
    if 'location' in existing_columns:
        with schema_editor.connection.cursor() as cursor:
            cursor.execute(
                f"SELECT {qn('id')}, {qn('location')} FROM {qn(table)} "
                f"WHERE {qn('location_id')} IS NULL AND {qn('location')} IS NOT NULL"
            )
            rows = cursor.fetchall()

        # rows contains (order_id, legacy_location_text)
        for order_id, legacy_text in rows:
            legacy = (legacy_text or '').strip()
            if not legacy:
                continue

            location_obj = Location.objects.filter(name__iexact=legacy).first()
            if location_obj is None:
                # Legacy data doesn't carry category; default to HALL.
                location_obj, _ = Location.objects.get_or_create(name=legacy, category='HALL')

            with schema_editor.connection.cursor() as cursor:
                cursor.execute(
                    f"UPDATE {qn(table)} SET {qn('location_id')} = %s WHERE {qn('id')} = %s",
                    [location_obj.id, order_id],
                )


class Migration(migrations.Migration):

    dependencies = [
        ('apis', '0030_remove_order_delivery_location_alter_order_location'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunPython(forwards_fix_order_location_db, migrations.RunPython.noop),
            ],
            state_operations=[
                # Update the migration state to match the current model:
                # - remove legacy delivery_location field
                # - change location from CharField to FK(Location)
                migrations.RemoveField(
                    model_name='order',
                    name='delivery_location',
                ),
                migrations.AlterField(
                    model_name='order',
                    name='location',
                    field=models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='orders',
                        to='apis.location',
                    ),
                ),
            ],
        ),
    ]
