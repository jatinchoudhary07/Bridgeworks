import http.client
import json
import time
from django.utils import timezone
import datetime

def get_valid_bluedart_token(shop):
    """
    Checks if the given shop's Blue Dart token is valid.
    If not, it requests a new one and saves it.
    """
    if shop.is_bluedart_token_valid():
        return shop.bluedart_jwt_token

    if not shop.bluedart_client_id or not shop.bluedart_client_secret:
        raise ValueError("Blue Dart credentials (ClientID / ClientSecret) are missing for this shop.")

    subdomain = "apigateway-sandbox" if shop.bluedart_api_type == "S" else "apigateway"
    host = f"{subdomain}.bluedart.com"
    endpoint = "/in/transportation/token/v1/login"

    headers = {
        'ClientID': shop.bluedart_client_id,
        'clientSecret': shop.bluedart_client_secret
    }

    try:
        conn = http.client.HTTPSConnection(host)
        conn.request("GET", endpoint, headers=headers)
        res = conn.getresponse()
        data = res.read()
        conn.close()

        if res.status == 200:
            response_data = json.loads(data.decode("utf-8"))
            if 'JWTToken' in response_data:
                token = response_data['JWTToken']
                # Token expires in exactly 24 hours, wait, Blue dart generally sets it.
                # Just set local expiry to 24 hours from now
                shop.bluedart_jwt_token = token
                shop.bluedart_jwt_expiry = timezone.now() + datetime.timedelta(hours=24)
                shop.save()
                return token
        
        raise Exception(f"Failed to get Blue Dart token. Status: {res.status}, Response: {data.decode('utf-8')}")

    except Exception as e:
        raise Exception(f"Error during Blue Dart token request: {str(e)}")


def submit_ndr_action(shop, awb_no, action_code, mobile_no="", landmark=""):
    """
    Submits an Alternate Instruction for an NDR parcel.
    action_code: e.g., 'DT', 'RTO', 'ED', 'SM', 'LM'
    """
    token = get_valid_bluedart_token(shop)

    if not shop.bluedart_login_id or not shop.bluedart_licence_key:
        raise ValueError("Blue Dart LoginID or LicenceKey is missing for this shop.")

    subdomain = "apigateway-sandbox" if shop.bluedart_api_type == "S" else "apigateway"
    host = f"{subdomain}.bluedart.com"
    endpoint = "/in/transportation/cust-instruction-update/v1/CustALTInstructionUpdate"

    # Unix timestamp in milliseconds for PreferDate
    current_time_ms = int(time.time() * 1000)
    prefer_date = f"/Date({current_time_ms})/"

    payload_dict = {
        "profile": {
            "LoginID": str(shop.bluedart_login_id),
            "Api_type": str(shop.bluedart_api_type),
            "LicenceKey": str(shop.bluedart_licence_key),
        },
        "altreq": {
            "MobileNo": str(mobile_no) if mobile_no else "",
            "AWBNo": str(awb_no),
            "PreferDate": prefer_date,
            "AltInstRequestType": str(action_code),
            "TimeSlot": "A",
            "LandMark": str(landmark).strip()[:50] if landmark else "",
        }
    }

    payload = json.dumps(payload_dict)

    headers = {
        'Content-Type': 'application/json',
        'JWTToken': token
    }

    try:
        print(f"--- BLUE DART ALT INSTRUCTION REQUEST ---")
        print(f"Endpoint: {host}{endpoint}")
        print(f"Payload: {payload}")
        print(f"-----------------------------------------")
        
        conn = http.client.HTTPSConnection(host)
        conn.request("POST", endpoint, body=payload, headers=headers)
        res = conn.getresponse()
        data = res.read()
        conn.close()

        response_str = data.decode("utf-8")
        print(f"--- BLUE DART ALT INSTRUCTION RESPONSE ---")
        print(f"Status: {res.status}")
        print(f"Response: {response_str}")
        print(f"------------------------------------------")
        
        if res.status in [200, 201]:
            try:
                response_data = json.loads(response_str)
                
                # Check for the expected {"CustALTInstructionUpdateResult": {...}} wrapper
                if isinstance(response_data, dict) and 'CustALTInstructionUpdateResult' in response_data:
                    res_body = response_data['CustALTInstructionUpdateResult']
                    is_error = res_body.get('IsError', True)
                    
                    status_list = res_body.get('status', [])
                    status_info_msg = ""
                    if isinstance(status_list, list) and len(status_list) > 0:
                        status_info_msg = status_list[0].get('StatusInformation', str(status_list[0]))
                    else:
                        status_info_msg = str(res_body)

                    return {
                        "IsError": is_error,
                        "StatusInformation": status_info_msg
                    }
                
                # Handle possible alternative Blue Dart response structures just in case
                if isinstance(response_data, dict) and 'Status' in response_data:
                    status_list = response_data['Status']
                    if isinstance(status_list, list) and len(status_list) > 0:
                        status_info = status_list[0]
                        return {
                            "IsError": status_info.get("IsError", True),
                            "StatusInformation": status_info.get("StatusInformation", str(response_data))
                        }
                
                # Fallback if structure is different
                return {
                    "IsError": False,
                    "StatusInformation": f"Request Successful: {response_str}"
                }

            except json.JSONDecodeError:
                return {
                    "IsError": True,
                    "StatusInformation": f"Failed to parse response: {response_str}"
                }
        else:
            return {
                "IsError": True,
                "StatusInformation": f"HTTP Error {res.status}: {response_str}"
            }

    except Exception as e:
        return {
            "IsError": True,
            "StatusInformation": f"Request Failed Exception: {str(e)}"
        }
