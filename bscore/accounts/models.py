'''
This module contains the models for the accounts app.
It includes the User, and OTP models.
These models are used to store information about the users, vendors, wallets 
and their otp information.

'''

import datetime
import decimal
import random
import string
from datetime import timedelta

from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import models
from django.utils import timezone

from bscore.utils.const import ConstList, UserType

from .manager import AccountManager


class User(AbstractBaseUser, PermissionsMixin):
    '''Custom User model for the application'''
    email = models.EmailField(max_length=50, unique=True)
    phone = models.CharField(max_length=12, unique=True)
    name = models.CharField(max_length=255)
    address = models.CharField(max_length=500, blank=True, null=True)
    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True)

    deleted = models.BooleanField(default=False)  # Soft delete
    user_type = models.CharField(max_length=20, default=UserType.CUSTOMER.value, choices=ConstList.USER_TYPE)
    
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    is_superuser = models.BooleanField(default=False)

    created_from_app = models.BooleanField(default=False)
    phone_verified = models.BooleanField(default=False)
    email_verified = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def vendor_profile(self) -> any:
        if self.user_type != UserType.VENDOR.value:
            return None
        vendor = Vendor.objects.filter(user=self).first()
        subscription = Subscription.objects.filter(vendor=vendor).order_by('-created_at').first()
        if vendor:
            return {
                'vendor_id': vendor.vendor_id,
                'vendor_name': vendor.vendor_name,
                'vendor_phone': vendor.vendor_phone,
                'vendor_email': vendor.vendor_email,
                'vendor_address': vendor.vendor_address,
                'subscription': subscription.package_name if subscription else None,
                'created_at': vendor.created_at,
            }
        return None

    objects = AccountManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['phone', 'name']

    def __str__(self):
        return self.name


class Vendor(models.Model):
    '''Vendor model for the application'''

    def generate_vendor_id():
        '''Generate a unique vendor id'''
        '''The vendor id is a random string of 8 characters'''
        pref = 'BNVD-'
        vendor_id = ''.join(random.choice(string.digits) for _ in range(8))
        return pref + vendor_id
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='vendor', blank=True, null=True)
    vendor_id = models.CharField(max_length=50, unique=True, default=generate_vendor_id)
    vendor_name = models.CharField(max_length=255)
    vendor_phone = models.CharField(max_length=12, unique=True)
    vendor_email = models.EmailField(max_length=50, unique=True)
    vendor_address = models.CharField(max_length=500, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def vendor_balance(self):
        wallet = Wallet.objects.filter(vendor=self).first()
        if wallet:
            return wallet.balance
        else:
            return 0.0

    @property
    def user_name(self):
        return self.user.name

    def send_welcome_sms(self) -> None:
        '''Send a welcome notification to the vendor'''
        from bscore.utils.services import send_sms
        msg = f'Welcome to the Birthnon Multi-vendor eCommerce Platform!\nYour Vendor Account ({self.vendor_name}) has been created successfully.\n\nRegards.\nThe Birthnon Team'
        send_sms(msg, [self.vendor_phone])
        print(msg)

    def create_wallet(self) -> None:
        '''Create a wallet for the vendor'''
        wallet = Wallet.objects.filter(vendor=self).first()
        if not wallet:
            wallet = Wallet.objects.create(vendor=self)
            wallet.save()
        else:
            return
        return 
    
    def get_wallet(self) -> any:
        '''Get the wallet for the vendor'''
        wallet = Wallet.objects.filter(vendor=self).first()
        return wallet
    
    def can_create_or_view_product(self) -> bool:
        '''Check if the vendor can create a product'''
        subscription = Subscription.objects.filter(vendor=self).order_by('-created_at').first()
        if subscription:
            return subscription.package.can_create_product
        return False
    
    def can_create_or_view_service(self) -> bool:
        '''Check if the vendor can create a service'''
        subscription = Subscription.objects.filter(vendor=self).order_by('-created_at').first()
        if subscription:
            return subscription.package.can_create_service
        return False
    
    def has_active_subscription(self) -> bool:
        '''Check if the vendor has an active subscription'''
        subscription = Subscription.objects.filter(vendor=self).order_by('-created_at').first()
        if subscription:
            return not subscription.expired
        return False

    def __str__(self):
        return self.vendor_name + ' - ' + self.user.name if self.user else self.vendor_id
    

class SubscriptionPackage(models.Model):
    '''Subscription package model for the application'''
    package_name = models.CharField(max_length=255)
    package_description = models.TextField()
    package_price = models.DecimalField(max_digits=10, decimal_places=2)
    can_create_product = models.BooleanField(default=False)
    can_create_service = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.package_name
    

class Subscription(models.Model):
    '''Subscription model for the application'''
    vendor = models.ForeignKey(Vendor, on_delete=models.CASCADE, null=True, blank=True)
    package = models.ForeignKey(SubscriptionPackage, on_delete=models.CASCADE)
    start_date = models.DateField(default=datetime.date.today)
    end_date = models.DateField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def expired(self):
        '''Check if the subscription is expired'''
        # NOTE: LATER, check payment status before checking expiry
        today = datetime.date.today()
        if self.end_date:
            return self.end_date < today
        if self.start_date:
            return (self.start_date + timedelta(days=30)) < today
        return (self.created_at + timedelta(days=30)).date() < today

    @property
    def vendor_name(self):
        return self.vendor.vendor_name
    
    @property
    def package_name(self):
        return self.package.package_name
    
    @property
    def payment_status(self):
        '''check if subscription has been paid for'''
        from apis.models import Payment
        payment = Payment.objects.filter(subscription=self).first()
        if payment:
            return payment.status
        return None

    @property
    def package_price(self):
        '''Gets the package price'''
        amount = self.package.package_price
        return amount

    # set the end date to 30 days from the start date
    def save(self, *args, **kwargs):
        if not self.end_date:
            self.end_date = self.start_date + timedelta(days=30)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.vendor.user_name + ' - ' + self.vendor.vendor_name + ' - ' + self.package.package_name


class Wallet(models.Model):
    '''Wallet model for the application'''
    def generate_wallet_id():
        '''Generate a unique wallet id'''
        '''The wallet id is a random string of 8 characters'''
        pref = 'BNWL-'
        wallet_id = ''.join(random.choice(string.digits) for _ in range(8))
        return pref + wallet_id

    wallet_id = models.CharField(max_length=50, unique=True, default=generate_wallet_id)
    vendor = models.ForeignKey(Vendor, on_delete=models.CASCADE)
    balance = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def credit_wallet(self, amount: float) -> None:
        '''Credit the wallet with the given amount'''
        self.balance += decimal.Decimal(amount)
        self.save()
        return
    
    def debit_wallet(self, amount: float) -> None:
        '''Debit the wallet with the given amount'''
        if self.balance >= decimal.Decimal(amount):
            self.balance -= decimal.Decimal(amount)
            self.save()
            return True
        else:
            return False

    def __str__(self):
        return self.wallet_id + ' - ' + self.vendor.vendor_name + ' - ' + str(self.balance)


class OTP(models.Model):
    '''One Time Password model'''
    phone = models.CharField(max_length=15, null=True, blank=True)
    otp = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def is_expired(self) -> bool:
        '''Returns True if the OTP is expired'''
        return (self.created_at + timedelta(minutes=30)) < timezone.now()
    
    def send_otp(self) -> None:
        '''Send the OTP to the user'''
        from bscore.utils.services import send_sms
        msg = f'Welcome to Birthnon.\n\nYour OTP is {self.otp}\n\nRegards,\nThe Birthnon Team!'
        send_sms(msg, [self.phone])
        print(msg)

    def __str__(self):
        return self.phone + ' - ' + str(self.otp)