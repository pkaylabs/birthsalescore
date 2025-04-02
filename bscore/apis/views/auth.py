from django.contrib.auth import login
from django.db.models import Q
from knox.models import AuthToken
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import OTP, User
from apis.serializers import (ChangePasswordSerializer, LoginSerializer, RegisterUserSerializer, ResetPasswordSerializer,
                              UserSerializer)
from bscore.utils.const import UserType

import random


class LoginAPI(APIView):
    '''Login api endpoint'''
    permission_classes = (permissions.AllowAny,)
    serializer_class = LoginSerializer

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

        # Delete existing token
        AuthToken.objects.filter(user=user).delete()
        return Response({
            "user": UserSerializer(user).data,
            "token": AuthToken.objects.create(user)[1],
        })


class VerifyOTPAPI(APIView):
    '''Verify OTP api endpoint'''
    permission_classes = (permissions.IsAuthenticated,)

    def get(self, request, *args, **kwargs):
        '''Use this endpoint to send OTP to the user'''
        user = request.user
        phone = user.phone
        code = random.randint(1000, 9999)
        try:
            OTP.objects.filter(phone=phone).delete()
            otp = OTP.objects.create(phone=phone, otp=code)
            otp.send_otp()
        except Exception as e:
            return Response({'error': 'Failed to send OTP'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        return Response({'message': 'OTP sent successfully'}, status=status.HTTP_200_OK)

    def post(self, request, *args, **kwargs):
        user = request.user
        phone = user.phone
        otp = request.data.get('otp')
        if not otp:
            return Response({'error': 'OTP is required'}, status=status.HTTP_400_BAD_REQUEST)
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
    '''Register api endpoint'''
    permission_classes = (permissions.AllowAny,)

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
            "user": UserSerializer(user).data,
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

    def get(self, request, *args, **kwargs):
        '''Get user profile'''
        user = request.user
        serializer = self.serializer_class(user)

        return Response(serializer.data, status=status.HTTP_200_OK)

    def put(self, request, *args, **kwargs):
        '''Update user profile'''
        user = request.user
        serializer = self.serializer_class(user, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    

class ChangePasswordAPIView(APIView):
    '''API endpoint to change user password'''

    permission_classes = (permissions.IsAuthenticated,)
    serializer_class = ChangePasswordSerializer

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