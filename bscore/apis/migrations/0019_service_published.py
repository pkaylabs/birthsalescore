# Generated by Django 5.1.5 on 2025-05-28 09:19

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('apis', '0018_servicebooking_location'),
    ]

    operations = [
        migrations.AddField(
            model_name='service',
            name='published',
            field=models.BooleanField(default=False),
        ),
    ]
