import array
import decimal
import random
import string
import time
import uuid

import requests
from rest_framework import status
from rest_framework.response import Response


from accounts.models import Vendor
from apis.models import Payment
from apis.serializers import PaymentSerializer
from bscore import settings
from bscore.utils.const import PaymentMethod, PaymentType


def send_sms(message: str, recipients: array.array, sender: str = settings.SENDER_ID):
    '''Sends an SMS to the specified recipients'''
    header = {"api-key": settings.ARKESEL_API_KEY, 'Content-Type': 'application/json',
              'Accept': 'application/json'}
    SEND_SMS_URL = "https://sms.arkesel.com/api/v2/sms/send"
    payload = {
        "sender": sender,
        "message": message,
        "recipients": recipients
    } 
    try:
        response = requests.post(SEND_SMS_URL, headers=header, json=payload)
    except Exception as e:
        print(f"Error: {e}")
        return False
    else:
        print(response.json())
        return response.json()
    

def collect_funds(data):
    '''To collect funds from user's momo' - debit user's account'''
    ENDPOINT = 'https://payhubghana.io/api/v1.0/debit_mobile_account/'
    headers = {
        "Authorization": f"Token {settings.PAYHUB_SECRET_TOKEN}",
    }
    print("Collecting funds from: ", data)
    response = requests.post(ENDPOINT, data=data, headers=headers)
    response_data = response.json()
    print("Collect funds response: ", response_data)
    return response_data


def disburse_funds(data):
    '''Disburse funds to user's momo - credit user's account'''
    ENDPOINT = 'https://payhubghana.io/api/v2.0/credit_mobile_account/'
    headers = {
        "Authorization": f"Token {settings.PAYHUB_SECRET_TOKEN}",
    }
    print("Disbursing funds to: ", data)
    response = requests.post(ENDPOINT, data=data, headers=headers)
    response_data = response.json()
    print("Disburse funds response: ", response_data)
    return response_data


def get_transaction_status(transaction_id):
    '''Check the status of a transaction'''
    ENDPOINT = 'https://payhubghana.io/api/v2.0/transaction_status'
    headers = {
        "Authorization": f"Token {settings.PAYHUB_SECRET_TOKEN}",
    }
    params = {
        "transaction_id": transaction_id,
    }
    response = requests.get(ENDPOINT, params=params, headers=headers)
    response_data = response.json()
    print("Transaction status: ", response_data)
    return response_data


def generate_transaction_id():
    '''Generate a unique transaction id'''
    return uuid.uuid4().hex[:14]


def generate_otp():
    '''generate a random otp for the user'''
    chars = string.digits
    size = 4
    return ''.join(random.choice(chars) for _ in range(size))


def can_cashout(request, amount: float = 0.0):
    '''Check if vendor can cashout'''
    user = request.user
    vendor = Vendor.objects.filter(user=user).first()
    if not vendor:
        return False
    wallet = vendor.get_wallet()
    if not wallet:
        return False
    if (wallet.balance < settings.MIN_CASHOUT_AMOUNT) or (wallet.balance < amount):
        return False
    return True

def get_payment_amount(request, cashout: bool = False, subscription = None, order = None, booking = None):
    '''get the amount to be paid'''
    if order:
        amount = order.get('amount', None)
    elif booking:
        amount = booking.get('amount', None)
    elif subscription:
        amount = subscription.package.package_price
    else:
        if cashout:
            # if it's a cashout, get the amount from the request data
            amount = request.data.get('amount', None)
        else:
            return {
                "message": "Order or booking or subscription is required",
                "api_status": status.HTTP_400_BAD_REQUEST
            }
    if amount is None:
        return {
            "message": "Amount is required",
            "api_status": status.HTTP_400_BAD_REQUEST
        }
    try:
        amount = decimal.Decimal(amount)
    except decimal.InvalidOperation:
        return {
            "message": "Invalid amount",
            "api_status": status.HTTP_400_BAD_REQUEST
        }
    if amount <= 0:
        return {
            "message": "Amount must be greater than 0",
            "api_status": status.HTTP_400_BAD_REQUEST
        }
    return {
        "amount": amount,
        "api_status": status.HTTP_200_OK
    }



def execute_momo_transaction(request, type, user=None, order=None, booking=None, subscription=None, vendor=None, withdrawal=False):
    '''
        Dusburse to or collect from user's momo.
        Parse [user] in case of a ussd request since it's not authenticated.
    '''
    if not withdrawal and (order is None and booking is None and subscription is None):
        # require order or booking or subscription only if not a withdrawal
        # this is because a withdrawal does not require an order or booking or subscription
        return {
            "transaction_status": "failed",
            "message": "Order or booking or subscription is required",
            "api_status": 400
        }
    user = request.user if user is None else user
    if vendor is None:
        return {
            "transaction_status": "failed",
            "message": "User is not a vendor",
            "api_status": 400
        }
    # check if vendor has a wallet
    if vendor.get_wallet() is None:
        return {
            "transaction_status": "failed",
            "message": "User does not have a wallet",
            "api_status": 400
        }
    print("Before wallet = vendor.get_wallet()")
    wallet = vendor.get_wallet()
    amount_res = get_payment_amount(request=request, cashout=withdrawal, subscription=subscription, order=order, booking=booking)
    if amount_res.get('api_status') != status.HTTP_200_OK:
        return {
            "transaction_status": "failed",
            "message": amount_res.get('message'),
            "api_status": amount_res.get('api_status')
        }
    amount = amount_res.get('amount')
    account_provider = request.data.get('network')
    phone = request.data.get('phone')

    print("generating transaction id")
    transaction_id = generate_transaction_id()  # generate a unique transaction id
    data = {
        'transaction_id': transaction_id,
        'mobile_number': phone,
        'amount': amount,
        'wallet_id': settings.PAYHUB_WALLET_ID,
        'network_code': account_provider,
    }

    print("Disbursing or collecting funds")
    # disburse or collect funds: depending on transaction type
    if type == PaymentType.CREDIT.value:
        disburse_funds(data)  # disburse funds to user / credit user's account
    elif type == PaymentType.DEBIT.value:
        collect_funds(data) # collect funds from user / debit user's account
    else:
        return Response({"message": "Invalid transaction type"}, status=status.HTTP_404_NOT_FOUND)

    print("Checking transaction status")
    transaction_is_successful = False
    # wait for 60 seconds: check status every 5 seconds
    for i in range(12):
        time.sleep(5)
        transaction_status = get_transaction_status(transaction_id)  # noqa
        if transaction_status['success'] == True:
            transaction_is_successful = True
            break

    print("Creating transaction")
    transaction = {
        'payment_id': data.get('transaction_id'),
        'status_code': transaction_status['status_code'],
        'status': transaction_status['message'],
        'order': order,
        'vendor': vendor,
        'booking': booking,
        'subscription': subscription,
        'user': user,
        'reason': 'Birthnon Payments',
        'payment_method': PaymentMethod.MOMO.value,
        'payment_type': type,
        'amount': amount,
    }

    transaction = Payment.objects.create(**transaction)
    serializer = PaymentSerializer(transaction, many=False)

    print("Debiting or crediting user wallet")
    if transaction_is_successful:
        # debit or credit user wallet: depending on transaction type
        if type == PaymentType.CREDIT.value:
            # it means the vendor did a cashout
            # debit vendor wallet
            success = wallet.debit_wallet(amount)
            if success:
                transaction.vendor_credited_debited = True
                transaction.save()
        elif type == PaymentType.DEBIT.value:
            # it means a client paid for a service/product/order
            # credit vendor wallet
            wallet.credit_wallet(amount)
            transaction.vendor_credited_debited = True
            transaction.save()
        else:
            print("CAN'T DETECT TRANSACTION TYPE")
        return {
            "transaction_status": "success",
            "message": "Transaction is successful",
            "transaction": serializer.data,
            "api_status": status.HTTP_200_OK
        }
    else:
        return {
            "transaction_status": "pending",
            "message": "Transaction is processing",
            "transaction": serializer.data,
            "api_status": status.HTTP_201_CREATED
        }
