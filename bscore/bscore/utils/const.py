from enum import Enum


class UserType(Enum):
    '''User types for the application'''
    CUSTOMER = 'CUSTOMER'
    VENDOR = 'VENDOR'
    ADMIN = 'ADMIN'
    DELIVERY = 'DELIVERY'


class ConstList:
    '''Lists for the application'''
    USER_TYPE = [
        (user_type.value, user_type.value) for user_type in UserType
    ]



class SubscriptionType(Enum):
    '''Subscription types for the application'''
    PRODUCT = 'PRODUCT SELLER'
    SERVICE = 'SERVICE PROVIDER'
    ELITE = 'BUSINESS ELITE'