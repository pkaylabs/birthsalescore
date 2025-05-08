from rest_framework import status
from rest_framework.permissions import BasePermission
from rest_framework.response import Response

from bscore.utils.const import UserType


class IsSuperuserOnly(BasePermission):
    """
    Allows access only to superusers.
    """
    def has_permission(self, request, view):
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
    
# decorator to allow/accept request from only specified domains
def allow_domains(allowed_domains):
    """
    Decorator to allow requests from specified domains.
    """
    def decorator(view_func):
        def _wrapped_view(request, *args, **kwargs):
            # Get the request domain
            request_domain = request.get_host()
            print(f"Request domain: {request_domain}")
            # Check if the request domain is in the allowed domains
            if request_domain not in allowed_domains:
                return Response({"detail": "Domain not allowed"}, status=status.HTTP_403_FORBIDDEN)
            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator