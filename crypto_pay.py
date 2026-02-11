import os
import requests
import hashlib
import hmac
from dotenv import load_dotenv

load_dotenv()

CRYPTO_PAY_TOKEN = os.getenv("CRYPTO_PAY_API_TOKEN")
NET = os.getenv("CRYPTO_BOT_NET", "testnet")

BASE_URL = "https://testnet-pay.crypt.bot/api" if NET == "testnet" else "https://pay.crypt.bot/api"

def get_headers():
    print(f"DEBUG: Token='{CRYPTO_PAY_TOKEN}', Net='{NET}', URL='{BASE_URL}'")
    return {
        "Crypto-Pay-API-Token": CRYPTO_PAY_TOKEN,
        "Content-Type": "application/json"
    }

def get_me():
    """Check if app is running."""
    url = f"{BASE_URL}/getMe"
    response = requests.get(url, headers=get_headers())
    return response.json()

def create_invoice(amount, currency="USD", description="Payment", payload=None):
    """
    Create an invoice.
    amount: float or string
    currency: "USD", "EUR", etc.
    payload: string (metadata, max 4kb)
    """
    url = f"{BASE_URL}/createInvoice"
    # User requested specific assets
    accepted_assets = "USDT,TON,BTC,ETH,LTC,BNB,TRX,USDC"
    
    data = {
        "amount": str(amount),
        "currency_type": "fiat",
        "fiat": currency,
        # "accepted_assets": accepted_assets,
        "description": description,
        "payload": payload
        # "allow_anonymous": False,
        # "allow_comments": False
    }
    
    response = requests.post(url, json=data, headers=get_headers())
    print(f"Create Invoice Response: {response.text}")
    return response.json()

def check_signature(body_text: str, signature: str) -> bool:
    """
    Verify Webhook signature.
    HMAC SHA-256
    """
    token = CRYPTO_PAY_TOKEN
    computed_signature = hmac.new(
        key=hashlib.sha256(token.encode()).digest(),
        msg=body_text.encode(),
        digestmod=hashlib.sha256
    ).hexdigest()
    
    return computed_signature == signature

def delete_invoice(invoice_id: int):
    """
    Delete an invoice.
    """
    url = f"{BASE_URL}/deleteInvoice"
    data = {"invoice_id": invoice_id}
    response = requests.post(url, json=data, headers=get_headers())
    return response.json()

def get_invoices(invoice_ids=None, status=None, limit=100, offset=0):
    """
    Get invoices of your app.
    invoice_ids: list or comma-separated string of IDs
    """
    url = f"{BASE_URL}/getInvoices"
    params = {}
    if invoice_ids:
        if isinstance(invoice_ids, list):
            params["invoice_ids"] = ",".join(map(str, invoice_ids))
        else:
            params["invoice_ids"] = str(invoice_ids)
            
    if status:
        params["status"] = status
        
    params["count"] = limit
    params["offset"] = offset
        
    response = requests.get(url, params=params, headers=get_headers())
    print(f"Get Invoices Response: {response.text}")
    return response.json()
