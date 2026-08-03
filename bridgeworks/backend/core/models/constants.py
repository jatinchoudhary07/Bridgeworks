from django.db import models
from django.db.models import JSONField, Count, Q
from django.contrib.auth import get_user_model
from django.conf import settings
from cryptography.fernet import Fernet
import os, uuid

User = get_user_model()

# ==============================================================================
# 0. CONSTANTS (The Source of Truth for NDRs)
# ==============================================================================
NDR_STATUSES = [
    "Future delivery requested",
    "Customer Refused",
    "Delivery Attempted-Premises Closed",
    "Attempted Delivery",
    "Consignee unavailable",
    "COD Payment Not Ready",
    "Undelivered",
    "Address Incorrect",
    "Pickup Failed",
    "Exception",
    "COD Not Ready",
    "Crta",
    "Consignee Refused to Accept",
    "Und",
    "Entry Restricted Area",
    "COD Payment Not Ready",
    "Customer refused - OTP verified",
    "Office/Residence Closed",
    "Consignee Not Available",
    "Customer Not Available",
    "Cna",
    "oda",
    "22",
    "25",
    # --- New mapped descriptions ---
    "Delivery Attempted",
    "Pending - Undelivered",
    "Delivery Exception",
    "Delivery Rescheduled",
    "Delivery Delayed",
    "Out of Delivery Area",
    "Network Issue",
    "On Hold",
    "Delivery Next Day",
    "Pick up Failed",
]

RTO_TRANSIT_STATUSES = [
    "Failure",
    "Return In Transit",
    "RTO Initiated",
    "RTO - In Transit",
    "Return - In Transit",
    "RTO - Initiated",
    "RTO - Delayed",
    "Rto Initiated",
    "Rto Delayed",
    "Rto",
    # Uppercase / courier variants found in DB
    "RTO IN TRANSIT",
    "RTO IN-TRANSIT",
    "Rto_In_Transit",
    "Rto In Transit",
    "RTO_IN_TRANSIT",
    "RETURN IN TRANSIT",
    "Return_In_Transit",
]

RTO_DELIVERED_STATUSES = [
    "RTO Delivered",
    "Return Delivered",
    "RTO - Delivered",
    "Return - Delivered",
    "RTO",
    # Uppercase / courier variants found in DB
    "RTO DELIVERED",
    "Rto Delivered",
    "Rto_Delivered",
    "RTO_DELIVERED",
    "RETURN DELIVERED",
    "Return_Delivered",
]

# --- Encryption Helpers ---
fernet = None
try:
    if settings.FERNET_KEY:
        FERNET_KEY = settings.FERNET_KEY.encode()
        fernet = Fernet(FERNET_KEY)
except Exception as e:
    print(f"CRITICAL: FERNET_KEY not loaded. Encryption/Decryption will fail. Error: {e}")
    
def encrypt_data(plain_text):
    if not fernet or not plain_text: return None
    return fernet.encrypt(plain_text.encode()).decode()

def decrypt_data(encrypted_text):
    if not fernet or not encrypted_text: return None
    try:
        return fernet.decrypt(encrypted_text.encode()).decode()
    except Exception: 
        return None
