from enum import Enum


class UserType(Enum):
    '''User types for the application'''
    CUSTOMER = 'CUSTOMER'
    VENDOR = 'VENDOR'
    ADMIN = 'ADMIN'
    DELIVERY = 'DELIVERY'


class PaymentStatus(Enum):
    '''Payment statuses for the application'''
    PENDING = 'PENDING'
    SUCCESS = 'SUCCESS'
    FAILED = 'FAILED'


class PaymentMethod(Enum):
    '''Payment methods for the application'''
    MOMO = 'MOMO'
    CASH = 'CASH'


class ConstList:
    '''Lists for the application'''
    USER_TYPE = [
        (user_type.value, user_type.value) for user_type in UserType
    ]

    PAYMENT_STATUS = [
        (payment_status.value, payment_status.value) for payment_status in PaymentStatus
    ]

    PAYMENT_METHOD = [
        (payment_method.value, payment_method.value) for payment_method in PaymentMethod
    ]


class SubscriptionType(Enum):
    '''Subscription types for the application'''
    PRODUCT = 'PRODUCT SELLER'
    SERVICE = 'SERVICE PROVIDER'
    ELITE = 'BUSINESS ELITE'