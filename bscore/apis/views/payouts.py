from django.db import transaction
from django.utils import timezone
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import Vendor
from apis.models import Payout
from apis.serializers import PayoutSerializer
from bscore.utils.const import UserType


class PayoutsAPIView(APIView):
    """List payouts.

    - Admin/staff/superuser: sees all payouts, can filter by vendor_id query param.
    - Vendor: sees only their payouts.
    """

    permission_classes = (permissions.IsAuthenticated,)

    def get(self, request, *args, **kwargs):
        user = request.user
        qs = Payout.objects.select_related('order', 'vendor', 'payment').prefetch_related('items', 'items__product').order_by('-created_at')

        vendor_id = request.query_params.get('vendor_id')
        payout_status = request.query_params.get('payout_status')
        payment_status = request.query_params.get('payment_status')

        is_admin = user.is_superuser or user.is_staff or user.user_type == UserType.ADMIN.value

        if is_admin:
            if vendor_id:
                qs = qs.filter(vendor__vendor_id=vendor_id)
        elif user.user_type == UserType.VENDOR.value:
            vendor = Vendor.objects.filter(user=user).first()
            if not vendor:
                return Response([], status=status.HTTP_200_OK)
            qs = qs.filter(vendor=vendor)
        else:
            return Response({"message": "Not allowed"}, status=status.HTTP_403_FORBIDDEN)

        if payout_status:
            qs = qs.filter(payout_status=payout_status)
        if payment_status:
            qs = qs.filter(payment_status=payment_status)

        serializer = PayoutSerializer(qs, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class ApprovePayoutAPIView(APIView):
    """Admin endpoint to approve/settle a payout and credit vendor wallet."""

    permission_classes = (permissions.IsAuthenticated,)

    def post(self, request, *args, **kwargs):
        user = request.user
        if not (user.is_superuser or user.is_staff or user.user_type == UserType.ADMIN.value):
            return Response({"message": "Not allowed"}, status=status.HTTP_403_FORBIDDEN)

        payout_id = request.data.get('payout_id')
        action = (request.data.get('action') or 'approve').lower()

        if not payout_id:
            return Response({"message": "payout_id is required"}, status=status.HTTP_400_BAD_REQUEST)

        payout = Payout.objects.select_related('vendor').filter(id=payout_id).first()
        if not payout:
            return Response({"message": "Payout not found"}, status=status.HTTP_404_NOT_FOUND)

        if action not in ['approve', 'reject']:
            return Response({"message": "Invalid action"}, status=status.HTTP_400_BAD_REQUEST)

        if action == 'reject':
            if payout.is_settled:
                return Response({"message": "Payout already settled"}, status=status.HTTP_400_BAD_REQUEST)
            payout.payout_status = 'REJECTED'
            payout.save()
            return Response({"status": "success", "message": "Payout rejected", "payout": PayoutSerializer(payout).data}, status=status.HTTP_200_OK)

        # Approve: credit vendor wallet once
        if payout.is_settled:
            return Response({"message": "Payout already settled"}, status=status.HTTP_400_BAD_REQUEST)

        vendor = payout.vendor
        wallet = vendor.get_wallet() if vendor else None
        if not wallet:
            return Response({"message": "Vendor wallet not found"}, status=status.HTTP_400_BAD_REQUEST)

        wallet.credit_wallet(payout.amount)
        payout.is_settled = True
        payout.settled_at = timezone.now()
        payout.settled_by = user
        payout.payout_status = 'APPROVED'
        payout.save()

        return Response({
            "status": "success",
            "message": "Payout approved and vendor credited",
            "payout": PayoutSerializer(payout).data,
        }, status=status.HTTP_200_OK)


class ApproveAllPendingPayoutsAPIView(APIView):
    """Admin endpoint to bulk-approve all pending payouts.

    Optional filter:
    - vendor_id: filter payouts by vendor.vendor_id (query param or request body)

    Notes:
    - Only approves payouts with payout_status == 'PENDING' and is_settled == False.
    - Rejected payouts are never approved because they are excluded by filter.
    """

    permission_classes = (permissions.IsAuthenticated,)

    def post(self, request, *args, **kwargs):
        user = request.user
        if not (user.is_superuser or user.is_staff or user.user_type == UserType.ADMIN.value):
            return Response({"message": "Not allowed"}, status=status.HTTP_403_FORBIDDEN)

        vendor_id = request.query_params.get('vendor_id') or request.data.get('vendor_id')

        qs = Payout.objects.select_related('vendor').filter(
            is_settled=False,
            payout_status='PENDING',
        )

        if vendor_id:
            qs = qs.filter(vendor__vendor_id=vendor_id)

        with transaction.atomic():
            payouts = list(qs.select_for_update())

            if not payouts:
                return Response({
                    "status": "success",
                    "message": "No pending payouts to approve",
                    "approved_count": 0,
                    "approved_payout_ids": [],
                }, status=status.HTTP_200_OK)

            missing_wallets = []
            for payout in payouts:
                vendor = payout.vendor
                wallet = vendor.get_wallet() if vendor else None
                if not wallet:
                    missing_wallets.append({
                        "payout_id": payout.id,
                        "vendor_id": vendor.vendor_id if vendor else None,
                        "vendor_name": vendor.vendor_name if vendor else None,
                    })

            if missing_wallets:
                return Response({
                    "message": "One or more vendor wallets not found; no payouts were approved",
                    "missing_wallets": missing_wallets,
                }, status=status.HTTP_400_BAD_REQUEST)

            approved_ids = []
            now = timezone.now()
            for payout in payouts:
                wallet = payout.vendor.get_wallet()
                wallet.credit_wallet(payout.amount)
                payout.is_settled = True
                payout.settled_at = now
                payout.settled_by = user
                payout.payout_status = 'APPROVED'
                payout.save()
                approved_ids.append(payout.id)

        return Response({
            "status": "success",
            "message": "Pending payouts approved and vendors credited",
            "approved_count": len(approved_ids),
            "approved_payout_ids": approved_ids,
        }, status=status.HTTP_200_OK)
