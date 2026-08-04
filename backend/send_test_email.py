import urllib.request
import urllib.error
import json
import os

API_KEY = os.getenv("SENDGRID_API_KEY", "").strip()
FROM_EMAIL = os.getenv("FROM_EMAIL", "sg@solacesquad.com").strip()
TO_EMAIL = os.getenv("TO_EMAIL", "sg@solacesquad.com").strip()

html_body = """<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family:-apple-system,BlinkMacSystemFont,Segoe UI,Roboto,sans-serif;background:#f3f4f6;margin:0;padding:24px;">
<div style="max-width:520px;margin:0 auto;background:#fff;border-radius:16px;overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,.1);">
  <div style="background:linear-gradient(135deg,#0f766e,#0d9488);padding:32px 28px;text-align:center;color:#fff;">
    <div style="font-size:2.5rem;margin-bottom:8px;">✅</div>
    <h1 style="margin:0;font-size:1.4rem;font-weight:700;">SolaceSquad Email Test</h1>
    <p style="margin:6px 0 0;opacity:.85;font-size:.875rem;">Confirming email delivery is working</p>
  </div>
  <div style="padding:32px 28px;">
    <p style="color:#111827;margin-top:0;">Hi <strong>Anantha</strong>,</p>
    <p style="color:#374151;">This is a test email from <strong>SolaceSquad</strong> confirming that SendGrid email delivery is <strong>fully operational</strong>.</p>
    <p style="color:#374151;">Password resets, appointment confirmations, and purchase emails should all be working now.</p>
    <p style="color:#6b7280;font-size:13px;margin-top:24px;"><em>— The SolaceSquad Team</em></p>
  </div>
  <div style="background:#f9fafb;padding:16px;text-align:center;font-size:12px;color:#9ca3af;border-top:1px solid #e5e7eb;">
    © 2026 SolaceSquad. All rights reserved.
  </div>
</div>
</body>
</html>"""

text_body = "Hi Anantha,\n\nThis is a test email from SolaceSquad confirming that SendGrid email delivery is fully operational.\n\nPassword resets, appointment confirmations, and purchase emails should all be working now.\n\n— The SolaceSquad Team"

payload = json.dumps({
    "personalizations": [{"to": [{"email": TO_EMAIL}]}],
    "from": {"email": FROM_EMAIL, "name": "SolaceSquad"},
    "subject": "SolaceSquad — Email Delivery Test ✅",
    "content": [
        {"type": "text/plain", "value": text_body},
        {"type": "text/html",  "value": html_body},
    ]
}).encode("utf-8")

req = urllib.request.Request(
    "https://api.sendgrid.com/v3/mail/send",
    data=payload,
    headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
    method="POST"
)

print(f"Sending from : {FROM_EMAIL}")
print(f"Sending to   : {TO_EMAIL}")
print(f"API key      : {API_KEY[:12]}...")

try:
    with urllib.request.urlopen(req, timeout=15) as r:
        print(f"\n[SUCCESS] HTTP {r.status}")
        print(f"    Email is on its way to {TO_EMAIL}!")
except urllib.error.HTTPError as e:
    body = e.read().decode("utf-8", errors="replace")
    print(f"\n[FAILED] HTTP {e.code}")
    print(f"    Error: {body}")
except Exception as ex:
    print(f"\n[ERROR] {ex}")
