import random

from django.contrib.auth import login
from knox.models import AuthToken
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser, FormParser
from drf_spectacular.utils import extend_schema, OpenApiExample, OpenApiResponse

from accounts.models import OTP, User
from apis.serializers import (ChangePasswordSerializer, LoginSerializer,
                              RegisterUserSerializer, ResetPasswordSerializer,
                              UserSerializer, UserAvatarSerializer)


class LoginAPI(APIView):
    '''Login api endpoint'''
    permission_classes = (permissions.AllowAny,)
    serializer_class = LoginSerializer

    @extend_schema(
        request=LoginSerializer,
        responses={
            200: OpenApiResponse(
                response=UserSerializer,
                description='Login successful',
                examples=[
                    OpenApiExample(
                        'Success Response',
                        value={
                            "user": {"id": 1, "email": "user@example.com", "name": "John Doe"},
                            "token": "abcd1234efgh5678ijkl9012mnop3456qrst7890"
                        }
                    )
                ]
            ),
            401: OpenApiResponse(description='Invalid credentials')
        },
        examples=[
            OpenApiExample(
                'Login Request',
                value={"email": "user@example.com", "password": "password123"},
                request_only=True
            )
        ]
    )
    def post(self, request, *args, **kwargs):
        serializer = self.serializer_class(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except Exception as e:
            print(e)
            for field in list(e.detail):
                error_message = e.detail.get(field)[0]
                field = f"{field}: " if field != "non_field_errors" else ""
                response_data = {
                    "status": "error",
                    "error_message": f"{field} {error_message}",
                    "user": None,
                    "token": None,
                }
                return Response(response_data, status=status.HTTP_401_UNAUTHORIZED)
        else:
            user = serializer.validated_data
       
        login(request, user)

        # now I am allowing multiple logins. 
        # Uncomment the following lines to delete existing tokens and allow only one active session per user.
        # Delete existing token
        # AuthToken.objects.filter(user=user).delete()
        return Response({
            "user": UserSerializer(user, context={'request': request}).data,
            "token": AuthToken.objects.create(user)[1],
        })

class VerifyOTPAPI(APIView):
    '''Verify OTP api endpoint'''
    permission_classes = (permissions.AllowAny,)

    def get(self, request, *args, **kwargs):
        '''Use this endpoint to send OTP to the user'''
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
        except Exception as e:
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
        otp = OTP.objects.filter(phone=phone, otp=otp).first()
        if not otp:
            return Response({'error': 'Invalid OTP'}, status=status.HTTP_400_BAD_REQUEST)
        if otp.is_expired():
            return Response({'error': 'OTP has expired'}, status=status.HTTP_400_BAD_REQUEST)
        otp.delete()
        user.phone_verified = True
        user.save()
        return Response({'message': 'OTP verified successfully'}, status=status.HTTP_200_OK)

class RegisterAPI(APIView):
    '''Register api endpoint -- When a user signs up on their own'''
    permission_classes = (permissions.AllowAny,)

    @extend_schema(
        request=RegisterUserSerializer,
        responses={
            200: OpenApiResponse(
                description='Registration successful',
                examples=[
                    OpenApiExample(
                        'Success',
                        value={
                            "user": {"id": 1, "email": "newuser@example.com", "name": "Jane Doe"},
                            "token": "abcd1234efgh5678ijkl9012mnop3456qrst7890"
                        }
                    )
                ]
            ),
            401: OpenApiResponse(description='Validation error')
        },
        examples=[
            OpenApiExample(
                'Register Request',
                value={
                    "email": "newuser@example.com",
                    "phone": "233200000000",
                    "password": "securepass123",
                    "name": "Jane Doe",
                    "user_type": "CUSTOMER"
                },
                request_only=True
            )
        ]
    )
    def post(self, request, *args, **kwargs):
        serializer = RegisterUserSerializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except Exception as e:
            for field in list(e.detail):
                error_message = e.detail.get(field)[0]
                field = f"{field}: " if field != "non_field_errors" else ""
                response_data = {
                    "status": "error",
                    "error_message": f"{field} {error_message}",
                    "user": None,
                    "token": None,
                }
                return Response(response_data, status=status.HTTP_401_UNAUTHORIZED)
        else:
            user = serializer.save()
        login(request, user)
        return Response({
            "user": UserSerializer(user, context={'request': request}).data,
            "token": AuthToken.objects.create(user)[1],
        })
    
class LogoutAPI(APIView):
    '''Logout api endpoint'''
    permission_classes = (permissions.IsAuthenticated,)

    def post(self, request, *args, **kwargs):
        user = request.user
        AuthToken.objects.filter(user=user).delete()
        return Response({"status": "success"}, status=status.HTTP_200_OK)
    

class UserProfileAPIView(APIView):
    '''API endpoint to get and update user profile'''

    permission_classes = (permissions.IsAuthenticated,)
    serializer_class = UserSerializer

    @extend_schema(
        responses={200: UserSerializer}
    )
    def get(self, request, *args, **kwargs):
        '''Get user profile'''
        user = request.user
        serializer = self.serializer_class(user, context={'request': request})

        return Response(serializer.data, status=status.HTTP_200_OK)

    @extend_schema(
        request=UserSerializer,
        responses={200: UserSerializer},
        examples=[
            OpenApiExample(
                'Update Profile',
                value={"name": "John Updated", "address": "New Address 123"},
                request_only=True
            )
        ]
    )
    def put(self, request, *args, **kwargs):
        '''Update user profile'''
        user = request.user
        serializer = self.serializer_class(user, data=request.data, partial=True, context={'request': request})
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    

class ChangePasswordAPIView(APIView):
    '''API endpoint to change user password'''

    permission_classes = (permissions.IsAuthenticated,)
    serializer_class = ChangePasswordSerializer

    @extend_schema(
        request=ChangePasswordSerializer,
        responses={
            200: OpenApiResponse(
                description='Password changed',
                examples=[
                    OpenApiExample('Success', value={"status": "success"})
                ]
            ),
            400: OpenApiResponse(description='Wrong password or validation error')
        },
        examples=[
            OpenApiExample(
                'Change Password',
                value={
                    "old_password": "oldpass123",
                    "new_password": "newpass456",
                    "confirm_password": "newpass456"
                },
                request_only=True
            )
        ]
    )
    def post(self, request, *args, **kwargs):
        '''Change user password'''
        user = request.user
        serializer = self.serializer_class(data=request.data)
        if serializer.is_valid():
            if not user.check_password(serializer.data.get('old_password')):
                return Response({'old_password': 'Wrong password.'}, status=status.HTTP_400_BAD_REQUEST)
            user.set_password(serializer.data.get('new_password'))
            user.save()
            return Response({'status': 'success'}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    

class ResetPasswordAPIView(APIView):
    '''API endpoint to reset user password'''

    permission_classes = (permissions.AllowAny,)
    serializer_class = ResetPasswordSerializer

    def post(self, request, *args, **kwargs):
        '''Reset user password'''
        serializer = self.serializer_class(data=request.data)
        if serializer.is_valid():
            phone = serializer.data.get('phone')
            user = User.objects.filter(phone=phone).first()
            if not user:
                return Response({'phone': 'User not found.'}, status=status.HTTP_400_BAD_REQUEST)
            if not user.phone_verified:
                return Response({'phone': 'Phone not verified.'}, status=status.HTTP_400_BAD_REQUEST)
            if len(serializer.data.get('new_password')) < 1:
                return Response({'new_password': 'Password is too short.'}, status=status.HTTP_400_BAD_REQUEST)
            if not serializer.data.get('new_password') == serializer.data.get('confirm_password'):
                return Response({'new_password': 'Passwords do not match.'}, status=status.HTTP_400_BAD_REQUEST)
            
            user.set_password(serializer.data.get('new_password'))
            user.save()
            return Response({'status': 'success'}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class UserProfileAvatarAPIView(APIView):
    '''API endpoint to update user profile picture (avatar)'''
    permission_classes = (permissions.IsAuthenticated,)
    parser_classes = (MultiPartParser, FormParser)

    @extend_schema(
        request={
            'multipart/form-data': {
                'type': 'object',
                'properties': {
                    'avatar': {
                        'type': 'string',
                        'format': 'binary'
                    }
                }
            }
        },
        responses={
            200: OpenApiResponse(
                description='Profile picture updated',
                examples=[
                    OpenApiExample(
                        'Success',
                        value={
                            "status": "success",
                            "message": "Profile picture updated successfully",
                            "avatar": "/media/avatars/user_profile.jpg"
                        }
                    )
                ]
            ),
            400: OpenApiResponse(description='Invalid file or validation error')
        }
    )
    def patch(self, request, *args, **kwargs):
        user = request.user
        serializer = UserAvatarSerializer(user, data=request.data, partial=True, context={'request': request})
        if serializer.is_valid():
            serializer.save()
            return Response({
                'status': 'success',
                'message': 'Profile picture updated successfully',
                'avatar': serializer.data['avatar']
            }, status=status.HTTP_200_OK)
        return Response({
            'status': 'error',
            'errors': serializer.errors,
            'error_message': str(next(iter(serializer.errors.values()))[0]) if serializer.errors else 'Invalid data',
        }, status=status.HTTP_400_BAD_REQUEST)