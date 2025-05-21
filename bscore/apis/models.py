import uuid

from django.db import models

from accounts.models import Subscription, User, Vendor
from bscore.utils.const import (ConstList, PaymentMethod, PaymentStatus,
                                PaymentType)


class ProductCategory(models.Model):
    """
    Model representing a product category.
    """
    name = models.CharField(max_length=255, unique=True)
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name
    
class Product(models.Model):
    """
    Model representing a product.
    """
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    category = models.ForeignKey(ProductCategory, on_delete=models.CASCADE, related_name='products')
    in_stock = models.BooleanField(default=True)
    is_published = models.BooleanField(default=False)
    vendor = models.ForeignKey(Vendor, on_delete=models.CASCADE, related_name='products', null=True, blank=True)
    image = models.ImageField(upload_to='products/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


    @property
    def vendor_name(self) -> str:
        '''get vendor name'''
        if self.vendor:
            return self.vendor.vendor_name
        return "Birthnon Services"

    def __str__(self):
        return self.name

class ProductImages(models.Model):
    """
    Model representing product images.
    """
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='product_images/')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Image for {self.product.name}"
    
class ProductReview(models.Model):
    """
    Model representing a product review.
    """
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='reviews')
    user = models.ForeignKey(Vendor, on_delete=models.CASCADE, related_name='reviews')
    rating = models.PositiveIntegerField()
    comment = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Review for {self.product.name} by {self.user.name}"

class OrderItem(models.Model):
    """
    Model representing an item in an order.
    """
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='order_items')
    quantity = models.PositiveIntegerField(default=1)
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)

    def save(self, *args, **kwargs):
        self.price = self.product.price * self.quantity
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.quantity} of {self.product.name} at GHC{self.price}"
    

class Order(models.Model):
    """
    Model representing an order.
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='orders')
    # order items will be limited: only Items belonging to the same vendor can be ordered at a time.
    items = models.ManyToManyField(OrderItem, related_name='orders')
    location = models.CharField(max_length=255, blank=True, null=True)
    customer_phone = models.CharField(max_length=15, blank=True, null=True)
    status = models.CharField(max_length=50, choices=[('Pending', 'Pending'), ('Completed', 'Completed'), ('Cancelled', 'Cancelled')], default='Pending')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def payment_status(self) -> str:
        '''check if order has been paid for'''
        payment = Payment.objects.filter(order=self).first()
        if payment:
            return payment.status
        return "None"
    
    @property
    def total_price(self) -> float:
        '''calculate total price of order'''
        total = 0.0
        for item in self.items.all():
            total += float(item.price * item.quantity)
        return total
    
    @property
    def vendor_id(self) -> str:
        item = self.items.first()
        return item.product.vendor.vendor_id if item else "None"
    
    @property
    def customer_name(self) -> str:
        '''get customer name'''
        if self.user:
            return self.user.name
        return "None"
    
    def notify_vendor_and_customer(self) -> None:
        '''Send notifications to the vendor and customer'''
        from bscore.utils.services import send_sms
        customer_msg = f'Hi, {self.customer_name}.\n\nThank you for shopping with us. We hope to see you soon.\n\nRegards.\nThe Birthnon Team'
        # notify customer
        send_sms(customer_msg, [self.user.phone])
        vendor_msg = f'Dear Vendor,\n\nA customer has placed a new order. Please login to your dashboard to see the order details.\n\nRegards.\nThe Birthnon Team'
        # notify vendor
        vendor = self.items.all().first().product.vendor
        send_sms(vendor_msg, [vendor.vendor_phone])

    def __str__(self):
        return f"Order {self.id} for {self.user.name}"    
    

class Service(models.Model):
    """
    Model representing a service.
    """
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    vendor = models.ForeignKey(Vendor, on_delete=models.CASCADE, related_name='services', null=True, blank=True)
    image = models.ImageField(upload_to='services/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def bookings(self) -> int:
        '''get all bookings for this service'''
        bookings = ServiceBooking.objects.filter(service=self).count()
        return bookings


    def __str__(self):
        return self.name


class Banner(models.Model):
    """
    Model representing a banner.
    """
    title = models.CharField(max_length=255)
    image = models.ImageField(upload_to='banners/')
    link = models.URLField(blank=True, null=True)
    is_active = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title


class Ad(models.Model):
    '''Model representing an Ad'''
    title = models.CharField(max_length=150)
    description = models.CharField(max_length=500)
    original_price = models.PositiveIntegerField(default=0)
    discount = models.PositiveIntegerField(default=0) # in percentage /100
    discount_type = models.CharField(max_length=50, choices=[('Percentage', 'Percentage'), ('Fixed', 'Fixed')], default='Percentage')
    end_date = models.DateField()

    @property
    def discounted_price(self) -> float:
        '''calculate discounted price'''
        if self.discount_type == 'Percentage':
            return self.original_price - (self.original_price * (self.discount / 100))
        elif self.discount_type == 'Fixed':
            return self.original_price - self.discount

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title
    
class AdImage(models.Model):
    '''Model representing an Ad image'''
    ad = models.ForeignKey(Ad, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='ads/')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.ad.title + " - " + str(self.id)


class ServiceBooking(models.Model):
    """Model for representing a service booking."""
    service = models.ForeignKey(Service, on_delete=models.CASCADE, related_name='bookings')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='service_bookings')
    date = models.DateField()
    time = models.TimeField()
    status = models.CharField(max_length=50, choices=[('Pending', 'Pending'), ('Confirmed', 'Confirmed'), ('Cancelled', 'Cancelled'), ('Completed', 'Completed')], default='Pending')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def payment_status(self) -> str:
        '''check if booking has been paid for'''
        payment = Payment.objects.filter(booking=self).first()
        if payment:
            return payment.status
        return "None"
    
    @property
    def service_name(self) -> str:
        return self.service.name
    
    @property
    def user_name(self) -> str:
        return self.user.name
    
    @property
    def vendor_name(self):
        return self.service.vendor.vendor_name
    
    def notify_vendor_and_customer(self) -> None:
        '''Send notifications to the vendor and customer'''
        from bscore.utils.services import send_sms
        customer_msg = f'Hi, {self.user_name}.\n\nThank you for booking a service with us. The Service Provider will contact you soon.\n\nRegards.\nThe Birthnon Team'
        # notify customer
        send_sms(customer_msg, [self.user.phone])
        vendor_msg = f'Dear Vendor,\n\nA customer ({self.user.phone}) has booked a new service ({self.service_name}). Please confirm the service on your dashboard.\n\nRegards.\nThe Birthnon Team'
        # notify vendor
        vendor = self.service.vendor
        send_sms(vendor_msg, [vendor.vendor_phone])

    def __str__(self):
        return f"Booking for {self.service.name} by {self.user.name} on {self.date} at {self.time}"


class Payment(models.Model):
    """
    Model representing a payment.
    Payment can either be for an order, a subscription or a service booking.
    """
    def get_payment_id():
        '''Generate a unique payment ID'''
        return uuid.uuid4().hex[:14]
    
    payment_id = models.CharField(max_length=255, unique=True, default=get_payment_id, editable=False)
    order = models.ForeignKey(Order, on_delete=models.PROTECT, related_name='payments', null=True)
    booking = models.ForeignKey(ServiceBooking, on_delete=models.PROTECT, related_name='payments', null=True)
    subscription = models.ForeignKey(Subscription, on_delete=models.PROTECT, related_name='payments', null=True)
    user = models.ForeignKey(User, on_delete=models.PROTECT, related_name='payments')
    vendor = models.ForeignKey(Vendor, on_delete=models.PROTECT, related_name='payments',  null=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    reason = models.CharField(max_length=255, blank=True, null=True)
    payment_method = models.CharField(max_length=10, choices=ConstList.PAYMENT_METHOD, default=PaymentMethod.MOMO.value)
    payment_type = models.CharField(max_length=10, choices=ConstList.PAYMENT_TYPE, default=PaymentType.DEBIT.value)
    status = models.CharField(max_length=10, default=PaymentStatus.PENDING.value)
    status_code = models.CharField(max_length=10, blank=True, null=True)
    vendor_credited_debited = models.BooleanField(default=False) # True if vendor has been credited or debited
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


    @property
    def what_was_paid_for(self) -> str:
        '''check if payment was for an order, subscription or booking'''
        if self.order:
            return "Payment for Order"
        elif self.booking:
            return "Payment for Booking"
        elif self.subscription:
            return "Payment for Subscription"
        else:
            return "None"
        
    @property
    def customer_name(self) -> str:
        '''get customer name'''
        if self.user:
            return self.user.name
        return "None"


    def __str__(self):
        msg = ''
        if self.order:
            msg = f"Payment for Order {self.order.id}"
        elif self.booking:
            msg = f"Payment for Booking {self.booking.id}"
        elif self.subscription:
            msg = f"Payment for Subscription {self.subscription.id}"
        else:
            msg = f"Payment for User {self.user.name}"
        return  f'{self.payment_id} - ' + msg
    

