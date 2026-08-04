import requests
import json

# Your MSG91 credentials
AUTH_KEY = "491737Ax0ZKYvzxRz69807d4bP1"
TEMPLATE_ID = "6a5241e382052452380ead06"
PHONE_NUMBER = "919901452664"  # Your test number

# Test OTP API
url = "https://api.msg91.com/api/v5/otp"

headers = {
    "authkey": AUTH_KEY,
    "content-type": "application/json"
}

payload = {
    "mobile": PHONE_NUMBER,
    "otp": "123456",
    "otp_expiry": "5",
    "template_id": TEMPLATE_ID
}

print("=" * 60)
print("MSG91 OTP API Test")
print("=" * 60)
print(f"URL: {url}")
print(f"Template ID: {TEMPLATE_ID}")
print(f"Phone: {PHONE_NUMBER}")
print(f"Payload: {json.dumps(payload, indent=2)}")
print("=" * 60)

try:
    response = requests.post(url, json=payload, headers=headers, timeout=10)
    print(f"\nResponse Status: {response.status_code}")
    print(f"Response Body: {response.text}")
    print(f"Response Headers: {dict(response.headers)}")
    
    if response.status_code == 200:
        print("\n[SUCCESS] API call successful!")
        print("If you don't receive SMS, the issue is with MSG91 template/account configuration.")
    else:
        print(f"\n[FAILED] API call failed: {response.status_code}")
        
except Exception as e:
    print(f"\n[ERROR] Error: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 60)
print("Check your phone for SMS with OTP: 123456")
print("Also check MSG91 Dashboard -> OTP Analytics")
print("=" * 60)
