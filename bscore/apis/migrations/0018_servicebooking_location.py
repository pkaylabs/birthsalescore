# Generated by Django 5.1.5 on 2025-05-25 12:17

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('apis', '0017_order_customer_phone'),
    ]

    operations = [
        migrations.AddField(
            model_name='servicebooking',
            name='location',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
    ]
