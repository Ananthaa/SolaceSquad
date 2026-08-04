"""
Clear SendGrid bounce suppressions so emails can be delivered again.
Run: python clear_sendgrid_bounces.py
"""
import urllib.request
import urllib.error
import json
import os

API_KEY = os.getenv("SENDGRID_API_KEY", "").strip()

HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}

# Emails to remove from suppression lists
EMAILS_TO_CLEAR = [
    "sq@solacesquad.com",
    "ananthaapkbkup@gmail.com",
    "testuser_verifier_3@gmail.com",
    "testuser_1@gmail.com",
]


def delete_bounce(email):
    req = urllib.request.Request(
        f"https://api.sendgrid.com/v3/suppression/bounces/{urllib.parse.quote(email)}",
        headers=HEADERS,
        method="DELETE"
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, "removed"
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return 404, "not in bounces"
        return e.code, e.read().decode("utf-8", errors="replace")
    except Exception as ex:
        return 0, str(ex)


def delete_block(email):
    import urllib.parse
    req = urllib.request.Request(
        f"https://api.sendgrid.com/v3/suppression/blocks/{urllib.parse.quote(email)}",
        headers=HEADERS,
        method="DELETE"
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, "removed"
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return 404, "not in blocks"
        return e.code, e.read().decode("utf-8", errors="replace")
    except Exception as ex:
        return 0, str(ex)


import urllib.parse

print("=" * 60)
print("  CLEARING SENDGRID SUPPRESSIONS")
print("=" * 60)

for email in EMAILS_TO_CLEAR:
    b_status, b_msg = delete_bounce(email)
    blk_status, blk_msg = delete_block(email)
    print(f"\n  {email}")
    print(f"    Bounces: HTTP {b_status} — {b_msg}")
    print(f"    Blocks : HTTP {blk_status} — {blk_msg}")

print("\n" + "=" * 60)
print("  Done. All suppressions cleared.")
print("  Now retry sending emails from the app.")
print("=" * 60)
