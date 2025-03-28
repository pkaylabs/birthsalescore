'''
This module contains the models for the accounts app.
It includes the User, and OTP models.
These models are used to store information about the users, vendors, wallets 
and their otp information.

'''

from datetime import timedelta, timezone
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import models
import string
import random
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
        if vendor:
            return {
                'vendor_id': vendor.vendor_id,
                'vendor_name': vendor.vendor_name,
                'vendor_phone': vendor.vendor_phone,
                'vendor_email': vendor.vendor_email,
                'vendor_address': vendor.vendor_address,
                'subscription': vendor.subscription.package_name if vendor.subscription else None,
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

    def __str__(self):
        return self.vendor_name + ' - ' + self.user.name if self.user else self.vendor_id
    

class SubscriptionPackage(models.Model):
    '''Subscription package model for the application'''
    package_name = models.CharField(max_length=255)
    package_description = models.TextField()
    package_price = models.DecimalField(max_digits=10, decimal_places=2)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.package_name
    

class Subscription(models.Model):
    '''Subscription model for the application'''
    vendor = models.ForeignKey(Vendor, on_delete=models.CASCADE)
    package = models.ForeignKey(SubscriptionPackage, on_delete=models.CASCADE)
    start_date = models.DateTimeField(auto_now_add=True)
    end_date = models.DateTimeField()

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # set the end date to 30 days from the start date
    def save(self, *args, **kwargs):
        if not self.end_date:
            self.end_date = self.start_date + timedelta(days=30)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.user.name + ' - ' + self.vendor.vendor_name + ' - ' + self.package.package_name


class Wallet(models.Model):
    '''Wallet model for the application'''
    vendor = models.ForeignKey(Vendor, on_delete=models.CASCADE)
    balance = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def credit_wallet(self, amount: float) -> None:
        '''Credit the wallet with the given amount'''
        self.balance += amount
        self.save()
        return
    
    def debit_wallet(self, amount: float) -> None:
        '''Debit the wallet with the given amount'''
        if self.balance >= amount:
            self.balance -= amount
            self.save()
            return True
        else:
            return False

    def __str__(self):
        return self.user.name + ' - ' + self.vendor.vendor_name + ' - ' + str(self.balance)


class OTP(models.Model):
    '''One Time Password model'''
    email = models.CharField(max_length=100)
    otp = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def is_expired(self) -> bool:
        '''Returns True if the OTP is expired'''
        return (self.created_at + timedelta(minutes=30)) < timezone.now()
    
    def send_otp_to_user(self) -> None:
        '''Send the OTP to the user'''
        msg = f'Welcome to the Destination Experience App.\nYour OTP is {self.otp}\n\nRegards,\nDXP Team'
        # send_mail([self.email], 'OTP', msg)
        print(msg)

    def __str__(self):
        return self.email + ' - ' + self.otp