from django.db import migrations, models


def seed_existing_stock(apps, schema_editor):
    Product = apps.get_model('apis', 'Product')
    Product.objects.filter(in_stock=True).update(stock_quantity=1)
    Product.objects.filter(in_stock=False).update(stock_quantity=0)


class Migration(migrations.Migration):

    dependencies = [
        ('apis', '0043_servicebooking_other_location'),
    ]

    operations = [
        migrations.AddField(
            model_name='product',
            name='stock_quantity',
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name='product',
            name='low_stock_threshold',
            field=models.PositiveIntegerField(default=5),
        ),
        migrations.RunPython(seed_existing_stock, migrations.RunPython.noop),
    ]
