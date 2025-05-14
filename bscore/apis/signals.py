import random

from django.db.models.signals import post_save
from django.dispatch import receiver

from accounts.models import OTP, User, Vendor
from apis.models import Order, Payment, ServiceBooking
from bscore.utils.const import PaymentStatusCode, PaymentType, UserType


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
    
@receiver(post_save, sender=Vendor)
def create_Vendor_wallet(sender, instance, created, **kwargs):
    if created:
        instance.create_wallet()

    return

@receiver(post_save, sender=Payment)
def debit_credit_vendor_wallet(sender, instance, created, **kwargs):
    '''Debit/credit vendor wallet'''
    if not created:
        '''only check for debit/credit on update'''
        if instance.vendor_credited_debited:
            # vendor has already been credited/debited
            return
        else:
            # check if payment is successful and not already credited/debited
            if instance.status_code == PaymentStatusCode.SUCCESS.value:
                # check if payment is credit or debit
                if instance.payment_type == PaymentType.CREDIT.value:
                    # it was a cashout... debit vendor wallet
                    wallet = instance.vendor.wallet

                    wallet.debit_wallet(instance.amount)
                    instance.vendor_credited_debited = True
                    instance.save()
                    pass
                elif instance.payment_type == 'debit':
                    # debit vendor wallet
                    instance.vendor.debit_wallet(instance.amount)
                # set vendor_credited_debited to True
                instance.vendor_credited_debited = True
                instance.save()
            else:
                # payment is not successful, do not credit/debit vendor wallet
                return
        return


@receiver(post_save, sender=ServiceBooking)
def notify_vendor_and_customer(sender, instance, created, **kwargs):
    if created:
        # notify vendor and customer of new service booking
        instance.notify_vendor_and_customer()
    return