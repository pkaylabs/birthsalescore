import random

from django.contrib.auth import login
from knox.models import AuthToken
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import OTP, User
from apis.serializers import (
    LoginSerializer,
    RegisterUserSerializer,
    UserSerializer,
    ChangePasswordSerializer,
    ContactSupportSerializer,
)
from bscore import settings


class MobileLoginAPI(APIView):
    """Mobile login endpoint (returns Knox token)."""

    permission_classes = (permissions.AllowAny,)
    serializer_class = LoginSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.serializer_class(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except Exception as e:
            # Normalize error response like the web API
            for field in list(getattr(e, 'detail', {})):
                error_message = e.detail.get(field)[0]
                field = f"{field}: " if field != "non_field_errors" else ""
                response_data = {
                    "status": "error",
                    "error_message": f"{field} {error_message}",
                    "user": None,
                    "token": None,
                }
                return Response(response_data, status=status.HTTP_401_UNAUTHORIZED)
            return Response({"status": "error"}, status=status.HTTP_401_UNAUTHORIZED)
        else:
            user = serializer.validated_data

        login(request, user)
        # Delete existing token to keep single active session behavior
        AuthToken.objects.filter(user=user).delete()
        return Response({
            "user": UserSerializer(user).data,
            "token": AuthToken.objects.create(user)[1],
        })


class MobileVerifyOTPAPI(APIView):
    """Send and verify OTP for mobile clients."""

    permission_classes = (permissions.AllowAny,)

    def get(self, request, *args, **kwargs):
        phone = request.query_params.get('phone')
        if not phone:
            return Response({'error': 'Phone number is required'}, status=status.HTTP_400_BAD_REQUEST)
        code = random.randint(1000, 9999)
        try:
            existingotp = OTP.objects.filter(phone=phone).first()
            if existingotp:
                existingotp.delete()
            user = User.objects.filter(phone=phone).first()
            if not user:
                return Response({'error': 'User account not found'}, status=status.HTTP_404_NOT_FOUND)
            otp = OTP.objects.create(phone=phone, otp=code)
            otp.send_otp()
        except Exception:
            return Response({'error': 'Failed to send OTP'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        return Response({'message': 'OTP sent successfully'}, status=status.HTTP_200_OK)

    def post(self, request, *args, **kwargs):
        otp = request.data.get('otp')
        phone = request.data.get('phone')
        user = User.objects.filter(phone=phone).first()
        if not user:
            return Response({'error': 'User account not found'}, status=status.HTTP_404_NOT_FOUND)
        if not phone:
            return Response({'error': 'Phone number is required'}, status=status.HTTP_400_BAD_REQUEST)
        if not otp:
            return Response({'error': 'Code is required'}, status=status.HTTP_400_BAD_REQUEST)
        otp_obj = OTP.objects.filter(phone=phone, otp=otp).first()
        if not otp_obj:
            return Response({'error': 'Invalid OTP'}, status=status.HTTP_400_BAD_REQUEST)
        if otp_obj.is_expired():
            return Response({'error': 'OTP has expired'}, status=status.HTTP_400_BAD_REQUEST)
        # OTP verified: mark verified, authenticate user and return token
        otp_obj.delete()
        user.phone_verified = True
        user.save()
        login(request, user)
        # Ensure single active token behavior
        # AuthToken.objects.filter(user=user).delete()
        return Response({
            'message': 'OTP verified successfully',
            'user': UserSerializer(user).data,
            'token': AuthToken.objects.create(user)[1],
        }, status=status.HTTP_200_OK)


class MobileRegisterAPI(APIView):
    """Mobile registration endpoint (returns Knox token)."""

    permission_classes = (permissions.AllowAny,)

    def post(self, request, *args, **kwargs):
        serializer = RegisterUserSerializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except Exception as e:
            for field in list(getattr(e, 'detail', {})):
                error_message = e.detail.get(field)[0]
                field = f"{field}: " if field != "non_field_errors" else ""
                response_data = {
                    "status": "error",
                    "error_message": f"{field} {error_message}",
                    "user": None,
                    "token": None,
                }
                return Response(response_data, status=status.HTTP_401_UNAUTHORIZED)
            return Response({"status": "error"}, status=status.HTTP_401_UNAUTHORIZED)
        else:
            user = serializer.save()

        login(request, user)
        return Response({
            "user": UserSerializer(user).data,
            "token": AuthToken.objects.create(user)[1],
        })


class MobileUserProfileAPIView(APIView):
    """Get and update authenticated user's profile for mobile clients."""

    permission_classes = (permissions.IsAuthenticated,)

    def get(self, request, *args, **kwargs):
        user = request.user
        return Response(UserSerializer(user).data, status=status.HTTP_200_OK)

    def put(self, request, *args, **kwargs):
        user = request.user
        serializer = UserSerializer(user, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class MobileChangePasswordAPI(APIView):
    """Change password for authenticated mobile users."""

    permission_classes = (permissions.IsAuthenticated,)
    serializer_class = ChangePasswordSerializer

    def post(self, request, *args, **kwargs):
        user = request.user
        serializer = self.serializer_class(data=request.data)
        if serializer.is_valid():
            if not user.check_password(serializer.validated_data.get('old_password')):
                return Response({
                    "status": "error",
                    "error_message": "Incorrect current password",
                    "errors": {"old_password": ["Incorrect current password"]},
                }, status=status.HTTP_400_BAD_REQUEST)
            user.set_password(serializer.validated_data.get('new_password'))
            user.save()
            return Response({
                'status': 'success',
                'message': 'Password updated successfully'
            }, status=status.HTTP_200_OK)
        # Return friendly, structured errors
        first_field = next(iter(serializer.errors), None)
        first_error = serializer.errors.get(first_field, ["Invalid data"])[0] if first_field else "Invalid data"
        return Response({
            "status": "error",
            "error_message": str(first_error),
            "errors": serializer.errors,
        }, status=status.HTTP_400_BAD_REQUEST)


class MobileContactSupportAPI(APIView):
    """Allow users (auth or guest) to contact support with name, email, phone, message."""

    permission_classes = (permissions.AllowAny,)
    serializer_class = ContactSupportSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.serializer_class(data=request.data)
        if serializer.is_valid():
            data = serializer.validated_data
            # Save message to database; signals will handle email notification
            from apis.models import ContactMessage
            cm = ContactMessage.objects.create(
                user=request.user if getattr(request, "user", None) and request.user.is_authenticated else None,
                name=data['name'],
                email=data['email'],
                phone=data['phone'],
                message=data['message'],
            )
            return Response({
                "status": "success",
                "message": "Your message has been received. Our support team will contact you soon.",
                "contact_message_id": cm.id,
            }, status=status.HTTP_200_OK)
        return Response({
            "status": "error",
            "errors": serializer.errors,
            "error_message": str(next(iter(serializer.errors.values()))[0]) if serializer.errors else "Invalid data",
        }, status=status.HTTP_400_BAD_REQUEST)
