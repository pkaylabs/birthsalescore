import array
import decimal
import random
import string
import time

import requests

from bscore import settings


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


def credit_user_wallet(user, amount):
    '''Credit user's wallet'''
    user.wallet.credit_wallet(decimal.Decimal(amount))
    return


def debit_user_wallet(user, amount):
    '''Debit user's wallet'''
    user.wallet.debit_wallet(decimal.Decimal(amount))
    return


def generate_transaction_id():
    '''Generate a unique transaction id'''
    pre = 'vttid'  # (vttid) : value transfer transaction id
    post = str(int(time.time() * 100000))[4:-1]
    return pre + post


def generate_otp():
    '''generate a random otp for the user'''
    chars = string.digits
    size = 4
    return ''.join(random.choice(chars) for _ in range(size))


def can_cashout(request, user: None, amount: decimal.Decimal):
    '''
        checks if the user can cashout: account is > 0 and account is > cashout amount.
        parse [user] in case of a ussd request since they are not autheticated.
    '''
    user_wallet = request.user.wallet if user is None else user.wallet
    return user_wallet.can_transfer_funds(amount)  # if funds is more than 0


def has_enough_balance(request, amount) -> bool:
    '''checks if the user has enough balance to topup'''
    user = request.user
    wallet = user.wallet
    amount = round(float(request.data.get('amount', "0")), 2)
    enough_balance = wallet.get_vt_balance() > amount  # if funds is more than amount
    if enough_balance:
        return True
    return False


def execute_momo_transaction(request, type, user: None):
    '''
        Dusburse to or collect from user's momo.
        Parse [user] in case of a ussd request since it's not authenticated.
    '''
    user = request.user if user is None else user
    wallet = user.wallet
    amount = request.data.get('amount')
    account_provider = request.data.get('network')
    reference = request.data.get('reference')
    phone = request.data.get('phone')

    # simulate returning a response
    return {
        "transaction_status": "success",
        "message": "Transaction is successful",
        "transaction": {
            "transaction_id": "1234567890",
            "status_code": "00",
            "status_message": "Transaction successful",
            "transaction_type": type,
            "destination_account": phone,
            "source_account": wallet.wallet_id,
            "destination_wallet": settings.PAYHUB_WALLET_ID,
            "source_wallet": wallet.wallet_id,
            "amount": amount,
            "reference": reference,
            "account_provider": account_provider,
        },
        "api_status": 200
    }
    # print("generating transaction id")
    # transaction_id = generate_transaction_id()  # generate a unique transaction id
    # data = {
    #     'transaction_id': transaction_id,
    #     'mobile_number': "",  # noqa
    #     'amount': amount,
    #     'wallet_id': settings.PAYHUB_WALLET_ID,
    #     'network_code': account_provider,
    # }

    # print("Disbursing or collecting funds")
    # # disburse or collect funds: depending on transaction type
    # if type == TransactionType.CASHOUT_VT.value:
    #     disburse_funds(data)  # disburse funds to user's momo
    # elif type == TransactionType.TOPUP_VT.value:
    #     collect_funds(data)
    # else:
    #     return Response({"message": "Invalid transaction type"}, status=status.HTTP_404_NOT_FOUND)

    # print("Checking transaction status")
    # transaction_is_successful = False  # flag to check if transaction was successful
    # # wait for 60 seconds: check status every 5 seconds
    # for i in range(12):
    #     time.sleep(5)
    #     transaction_status = get_transaction_status(transaction_id)  # noqa
    #     if transaction_status['success'] == True:
    #         transaction_is_successful = True
    #         break

    # print("Creating transaction")
    # transaction = {
    #     'transaction_id': data.get('transaction_id'),
    #     'status_code': transaction_status['status_code'],
    #     'status_message': transaction_status['message'],
    #     'transaction_type': type,
    #     'destination_account': destination_account,
    #     'source_account': source_account,
    #     'destination_wallet': destination_wallet,
    #     'source_wallet': source_wallet,
    #     'amount': amount,
    #     'reference': reference,
    #     'account_provider': account_provider,
    # }

    # transaction = Transaction.objects.create(**transaction)
    # serializer = TransactionSerializer(transaction, many=False)

    # print("Debiting or crediting user wallet")
    # if transaction_is_successful:
    #     # debit or credit user wallet: depending on transaction type
    #     if type == TransactionType.CASHOUT_VT.value:
    #         debit_user_wallet(user, amount)
    #     elif type == TransactionType.TOPUP_VT.value:
    #         credit_user_wallet(user, amount)
    #     else:
    #         print("CAN'T DETECT TRANSACTION TYPE")
    #     return {
    #         "transaction_status": "success",
    #         "message": "Transaction is successful",
    #         "transaction": serializer.data,
    #         "api_status": status.HTTP_200_OK
    #     }
    # else:
    #     return {
    #         "transaction_status": "pending",
    #         "message": "Transaction is processing",
    #         "transaction": serializer.data,
    #         "api_status": status.HTTP_201_CREATED
    #     }
