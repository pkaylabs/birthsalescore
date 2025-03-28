import random

from django.db.models.signals import post_save
from django.dispatch import receiver

from accounts.models import OTP, User, Vendor
from bscore.utils.const import UserType


@receiver(post_save, sender=User)
def otp_and_welcome_vendor(sender, instance, created, **kwargs):
    if created:
        if instance.is_superuser or instance.phone_verified or instance.email_verified:
            # do not create otp for superuser or already verified users
            return
        otp = random.randint(1000, 9999)
        otp = OTP.objects.create(phone=instance.phone, otp=otp)
        print(f"OTP for {instance.phone} is {otp}")

        # send otp
        otp.send_otp()

        # check if user is vendor
        if instance.user_type == UserType.VENDOR.value:
            vendor = Vendor.objects.filter(user=instance).first()
            if not vendor:
                # create vendor if not exists
                vendor = Vendor.objects.create(
                    user=instance,
                    vendor_name=instance.name,
                    vendor_phone=instance.phone,
                    vendor_email=instance.email,
                    vendor_address=instance.address,
                )
            # notify vendor of their account creation
            vendor.send_welcome_sms()

            # create wallet for vendor
            vendor.create_wallet()
        return
    
