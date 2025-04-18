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


class ServiceStatus(Enum):
    '''Service statuses for the application'''
    PENDING = 'PENDING'
    ACCEPTED = 'ACCEPTED'
    REJECTED = 'REJECTED'
    COMPLETED = 'COMPLETED'


class PaymentMethod(Enum):
    '''Payment methods for the application'''
    MOMO = 'MOMO'
    CASH = 'CASH'


class PaymentType(Enum):
    '''Payment types for the application'''
    DEBIT = 'DEBIT'
    CREDIT = 'CREDIT'

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

    PAYMENT_TYPE = [
        (payment_type.value, payment_type.value) for payment_type in PaymentType
    ]

    SERVICE_STATUS = [
        (service_status.value, service_status.value) for service_status in ServiceStatus
    ]


class SubscriptionType(Enum):
    '''Subscription types for the application'''
    PRODUCT = 'PRODUCT SELLER'
    SERVICE = 'SERVICE PROVIDER'
    ELITE = 'BUSINESS ELITE'