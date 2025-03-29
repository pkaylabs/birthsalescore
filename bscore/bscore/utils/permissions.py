from rest_framework.permissions import BasePermission

from bscore.utils.const import UserType


class IsSuperuser(BasePermission):
    """
    Allows access only to superusers.
    """
    def has_permission(self, request):
        return request.user.is_authenticated and request.user.is_superuser


class IsAdminOnly(BasePermission):
    """
    Allows access to admin or staff users only
    """
    def has_permission(self, request, view):
        user = request.user
        is_staff = user.is_staff
        is_admin = (user.user_type == UserType.ADMIN.value)
        return user.is_authenticated and (is_staff or is_admin)


class IsCustomerOnly(BasePermission):
    '''
    Allow access to customer users only.
    '''
    def has_permission(self, request, view):
        user = request.user
        is_customer = user.user_type == UserType.CUSTOMER.value
        return user.is_authenticated and is_customer
    

class IsEliteVendorOnly(BasePermission):
    '''
    Allow access to vendor users only.
    '''
    def has_permission(self, request, view):
        user = request.user
        is_vendor = user.user_type == UserType.VENDOR.value
        return user.is_authenticated and is_vendor