"""
exotel_service.py — Exotel Telephony Call Bridging for SolaceSquad Quick Consultations.

Bridges phone calls between clients and wellness consultants at appointment start time.
Preserves client and consultant privacy by using SolaceSquad virtual caller ID (DPDP Act 2023 compliance).

Zero Hardcoded Secrets:
All credentials are read dynamically from Google Secret Manager / Environment:
  - EXOTEL_API_KEY
  - EXOTEL_API_TOKEN
  - EXOTEL_SID
  - EXOTEL_CALLER_ID
"""

import os
import requests
import secrets
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger("exotel_service")


def _format_exotel_phone(phone: str) -> str:
    """
    Format phone number for Exotel API.
    Removes whitespace, hyphens, and leading +; ensures 10/11-digit domestic format or E.164.
    """
    cleaned = "".join(ch for ch in str(phone) if ch.isdigit() or ch == "+")
    if cleaned.startswith("+91"):
        cleaned = cleaned[3:]
    elif cleaned.startswith("91") and len(cleaned) == 12:
        cleaned = cleaned[2:]
    
    # Exotel domestic standard in India: 10 digits prefixed with 0 (e.g., 09876543210)
    if len(cleaned) == 10:
        return f"0{cleaned}"
    elif len(cleaned) == 11 and cleaned.startswith("0"):
        return cleaned
    
    # Fallback to cleaned original
    return cleaned


def _clean_val(val: Optional[str]) -> str:
    if not val:
        return ""
    return str(val).strip().strip('"').strip("'").strip()


def is_exotel_configured() -> bool:
    """Check if Exotel credentials are set in environment variables."""
    api_key = _clean_val(os.getenv("EXOTEL_API_KEY"))
    api_token = _clean_val(os.getenv("EXOTEL_API_TOKEN"))
    sid = _clean_val(os.getenv("EXOTEL_SID"))
    caller_id = _clean_val(os.getenv("EXOTEL_CALLER_ID"))
    return bool(api_key and api_token and sid and caller_id)


def bridge_quick_consult_call(
    from_phone: str,
    to_phone: str,
    duration_minutes: int = 30,
    qc_id: Optional[str] = None,
    callback_url: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Bridge a phone call between Consultant and User via Exotel.
    
    Args:
        from_phone: Consultant's mobile number
        to_phone: User's mobile number
        duration_minutes: Session limit (30 or 60 minutes)
        qc_id: SolaceSquad Quick Consultation ID (e.g. SS_A8K9X)
        callback_url: Webhook URL for call status / duration events
        
    Returns:
        Dict: {"success": bool, "call_sid": str, "message": str, "is_mock": bool}
    """
    api_key = _clean_val(os.getenv("EXOTEL_API_KEY"))
    api_token = _clean_val(os.getenv("EXOTEL_API_TOKEN"))
    sid = _clean_val(os.getenv("EXOTEL_SID"))
    caller_id = _clean_val(os.getenv("EXOTEL_CALLER_ID"))

    fmt_from = _format_exotel_phone(from_phone)
    fmt_to = _format_exotel_phone(to_phone)
    time_limit_sec = int(duration_minutes * 60)

    # Safe Mock / Staging Mode when Exotel credentials are not configured
    if not (api_key and api_token and sid and caller_id):
        mock_sid = f"mock_exo_{qc_id or secrets.token_hex(4)}"
        print(
            f"[EXOTEL-STAGING] Mock Call Bridge initiated: "
            f"From={fmt_from} -> To={fmt_to} | CallerId={caller_id or 'VIRTUAL_NUMBER'} "
            f"| Limit={time_limit_sec}s | QC_ID={qc_id} | SID={mock_sid}"
        )
        return {
            "success": True,
            "call_sid": mock_sid,
            "message": "Call bridging initiated in staging mode.",
            "is_mock": True,
        }

    try:
        clean_caller = "".join(ch for ch in str(caller_id) if ch.isdigit())
        if len(clean_caller) == 10 and not clean_caller.startswith("0"):
            clean_caller = f"0{clean_caller}"

        url = f"https://api.exotel.com/v1/Accounts/{sid}/Calls/connect.json"
        payload = {
            "From": fmt_from,
            "To": fmt_to,
            "CallerId": clean_caller,
            "CallType": "trans",
            "TimeLimit": str(time_limit_sec),
        }

        if callback_url:
            payload["StatusCallback"] = callback_url
        if qc_id:
            payload["CustomField"] = qc_id

        print(f"[EXOTEL] Triggering connect API for QC_ID {qc_id}: From={fmt_from}, To={fmt_to}, CallerId={clean_caller}")
        response = requests.post(
            url,
            data=payload,
            auth=(api_key, api_token),
            timeout=15,
        )

        if response.status_code in (200, 201):
            res_json = response.json()
            call_obj = res_json.get("Call", {})
            call_sid = call_obj.get("Sid") or res_json.get("Sid") or f"exo_{qc_id}"
            print(f"[EXOTEL] ✅ Call bridged successfully. Call SID: {call_sid}")
            return {
                "success": True,
                "call_sid": call_sid,
                "message": "Call bridged successfully",
                "is_mock": False,
                "data": res_json,
            }
        else:
            err_msg = f"Exotel API error {response.status_code}: {response.text}"
            print(f"[EXOTEL] ❌ {err_msg}")
            return {
                "success": False,
                "call_sid": None,
                "message": err_msg,
                "is_mock": False,
            }

    except Exception as exc:
        err_msg = f"Exotel call bridge exception: {str(exc)}"
        print(f"[EXOTEL] ❌ {err_msg}")
        return {
            "success": False,
            "call_sid": None,
            "message": err_msg,
            "is_mock": False,
        }
