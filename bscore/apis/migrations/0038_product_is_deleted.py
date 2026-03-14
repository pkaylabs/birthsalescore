from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('apis', '0037_alter_payment_booking_alter_payment_order_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='product',
            name='is_deleted',
            field=models.BooleanField(db_index=True, default=False),
        ),
    ]
