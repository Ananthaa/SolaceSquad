"""
SendGrid Email Integration for SolaceSquad
"""

import os
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Email, To, Content
from typing import Optional


def send_password_reset_email(to_email: str, user_name: str, reset_link: str) -> bool:
    """
    Send password reset email using SendGrid
    
    Args:
        to_email: Recipient email address
        user_name: User's name for personalization
        reset_link: Full password reset URL with token
        
    Returns:
        True if email sent successfully, False otherwise
    """
    try:
        # Get SendGrid API key from environment
        sendgrid_api_key = os.getenv("SENDGRID_API_KEY")
        from_email = os.getenv("FROM_EMAIL", "noreply@solacesquad.com")

        # Strip any trailing whitespace/newlines added by Secret Manager
        if sendgrid_api_key:
            sendgrid_api_key = sendgrid_api_key.strip()

        print(f"[SendGrid] FROM_EMAIL={from_email}")
        print(f"[SendGrid] API key found: {'YES, prefix=' + sendgrid_api_key[:12] if sendgrid_api_key else 'NO - NOT SET'}")

        if not sendgrid_api_key:
            print("⚠️  WARNING: SENDGRID_API_KEY not configured")
            print(f"📧 Password reset link for {to_email}:")
            print(f"   {reset_link}")
            return False

        # Create email content
        subject = "Reset Your SolaceSquad Password"

        # HTML email template
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
                    line-height: 1.6;
                    color: #333;
                    max-width: 600px;
                    margin: 0 auto;
                    padding: 0;
                }}
                .container {{
                    background: #ffffff;
                    border-radius: 12px;
                    overflow: hidden;
                    box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
                }}
                .header {{
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    color: white;
                    padding: 40px 30px;
                    text-align: center;
                }}
                .header h1 {{
                    margin: 0;
                    font-size: 28px;
                    font-weight: 600;
                }}
                .content {{
                    padding: 40px 30px;
                    background: #f9fafb;
                }}
                .button {{
                    display: inline-block;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    color: white !important;
                    padding: 16px 32px;
                    text-decoration: none;
                    border-radius: 8px;
                    margin: 24px 0;
                    font-weight: 600;
                    font-size: 16px;
                }}
                .link-box {{
                    background: white;
                    padding: 15px;
                    border-radius: 6px;
                    word-break: break-all;
                    border: 1px solid #e5e7eb;
                    margin: 20px 0;
                    font-size: 14px;
                    color: #6b7280;
                }}
                .warning {{
                    background: #fef3c7;
                    border-left: 4px solid #f59e0b;
                    padding: 16px;
                    margin: 24px 0;
                    border-radius: 4px;
                }}
                .footer {{
                    text-align: center;
                    padding: 30px;
                    color: #6b7280;
                    font-size: 14px;
                    background: #f9fafb;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>SolaceSquad</h1>
                    <p style="margin: 10px 0 0 0; font-size: 16px;">Password Reset Request</p>
                </div>

                <div class="content">
                    <p style="font-size: 16px; margin-bottom: 20px;">Hi {user_name},</p>

                    <p>We received a request to reset your password for your SolaceSquad account. Click the button below to create a new password:</p>

                    <center>
                        <a href="{reset_link}" class="button">Reset Password</a>
                    </center>

                    <p style="margin-top: 30px;">Or copy and paste this link into your browser:</p>
                    <div class="link-box">
                        {reset_link}
                    </div>

                    <div class="warning">
                        <strong>Important:</strong> This link will expire in 1 hour. If you did not request this password reset, please ignore this email.
                    </div>

                    <p style="margin-top: 30px;">Best regards,<br>The SolaceSquad Team</p>
                </div>

                <div class="footer">
                    <p>This is an automated email. Please do not reply to this message.</p>
                    <p>&copy; 2026 SolaceSquad. All rights reserved.</p>
                </div>
            </div>
        </body>
        </html>
        """

        # Plain text version
        text_content = f"""Hi {user_name},

We received a request to reset your password for your SolaceSquad account.

Click the link below to create a new password:
{reset_link}

This link will expire in 1 hour.

If you did not request this password reset, please ignore this email.

Best regards,
The SolaceSquad Team
"""

        # Use simple HTTP request instead of SendGrid SDK to avoid library issues
        import urllib.request
        import json as _json

        payload = _json.dumps({
            "personalizations": [{"to": [{"email": to_email}]}],
            "from": {"email": from_email, "name": "SolaceSquad"},
            "subject": subject,
            "content": [
                {"type": "text/plain", "value": text_content},
                {"type": "text/html",  "value": html_content}
            ],
            "tracking_settings": {
                "click_tracking": {
                    "enable": False,
                    "enable_text": False
                }
            }
        }).encode("utf-8")

        req = urllib.request.Request(
            "https://api.sendgrid.com/v3/mail/send",
            data=payload,
            headers={
                "Authorization": f"Bearer {sendgrid_api_key}",
                "Content-Type": "application/json"
            },
            method="POST"
        )

        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                status = resp.status
                print(f"SUCCESS: Password reset email sent to {to_email} | HTTP {status}")
                return True
        except urllib.error.HTTPError as http_err:
            body = http_err.read().decode("utf-8", errors="replace")
            print(f"ERROR: SendGrid HTTP {http_err.code}: {body}")
            print(f"📧 Reset link for {to_email}: {reset_link}")
            return False

    except Exception as e:
        print(f"ERROR: Error sending password reset email: {type(e).__name__}: {str(e)}")
        print(f"📧 Reset link for {to_email}: {reset_link}")
        return False


def send_welcome_email(to_email: str, user_name: str) -> bool:
    """
    Send welcome email to new user using SendGrid
    
    Args:
        to_email: Recipient email address
        user_name: User's name for personalization
        
    Returns:
        True if email sent successfully, False otherwise
    """
    try:
        sendgrid_api_key = os.getenv("SENDGRID_API_KEY")
        from_email = os.getenv("FROM_EMAIL", "noreply@solacesquad.com")
        
        if not sendgrid_api_key:
            print(f"Welcome email would be sent to {to_email}")
            return False
        
        subject = "Welcome to SolaceSquad! 🧘"
        
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                    line-height: 1.6;
                    color: #333;
                    max-width: 600px;
                    margin: 0 auto;
                }}
                .container {{
                    background: #ffffff;
                    border-radius: 12px;
                    overflow: hidden;
                    box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
                }}
                .header {{
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    color: white;
                    padding: 40px 30px;
                    text-align: center;
                }}
                .content {{
                    padding: 40px 30px;
                    background: #f9fafb;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>🧘 Welcome to SolaceSquad!</h1>
                </div>
                <div class="content">
                    <p>Hi {user_name},</p>
                    <p>Thank you for joining SolaceSquad! We're excited to support you on your wellbeing journey.</p>
                    <p>Get started by exploring our features and connecting with our professional consultants.</p>
                    <p>Best regards,<br>The SolaceSquad Team</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        text_content = f"Hi {user_name},\n\nWelcome to SolaceSquad! We're excited to support you on your wellbeing journey.\n\nBest regards,\nThe SolaceSquad Team"
        
        from sendgrid.helpers.mail import TrackingSettings, ClickTracking
        tracking_settings = TrackingSettings()
        tracking_settings.click_tracking = ClickTracking(enable=False, enable_text=False)

        message = Mail(
            from_email=Email(from_email, "SolaceSquad"),
            to_emails=To(to_email),
            subject=subject,
            plain_text_content=Content("text/plain", text_content),
            html_content=Content("text/html", html_content)
        )
        message.tracking_settings = tracking_settings
        
        sg = SendGridAPIClient(sendgrid_api_key)
        response = sg.send(message)
        
        print(f"SUCCESS: Welcome email sent to {to_email}")
        return True
        
    except Exception as e:
        print(f"ERROR: Error sending welcome email: {str(e)}")
        return False


# ──────────────────────────────────────────────────────────────────────────────────────────────────
# Appointment email  (booking confirmation + .ics calendar invite / cancellation)
# ──────────────────────────────────────────────────────────────────────────────────────────────────

def _send_raw_appt(to_email: str, subject: str, html: str, text: str,
                   attachments: list = None) -> bool:
    """Fire a single email via the SendGrid v3 HTTP API."""
    import json as _json, urllib.request, urllib.error
    api_key   = (os.getenv("SENDGRID_API_KEY") or "").strip()
    from_addr = os.getenv("FROM_EMAIL", "noreply@solacesquad.com")
    if not api_key:
        print(f"[SendGrid] No API key — skipping email to {to_email}")
        return False

    payload: dict = {
        "personalizations": [{"to": [{"email": to_email}]}],
        "from":    {"email": from_addr, "name": "SolaceSquad"},
        "subject": subject,
        "content": [
            {"type": "text/plain", "value": text},
            {"type": "text/html",  "value": html},
        ],
        "tracking_settings": {
            "click_tracking": {
                "enable": False,
                "enable_text": False
            }
        }
    }
    if attachments:
        payload["attachments"] = attachments

    req = urllib.request.Request(
        "https://api.sendgrid.com/v3/mail/send",
        data=_json.dumps(payload).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key}",
                 "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            print(f"[SendGrid] SUCCESS: '{subject}' -> {to_email} ({r.status})")
            return True
    except urllib.error.HTTPError as e:
        print(f"[SendGrid] ERROR: HTTP {e.code}: {e.read().decode('utf-8','replace')}")
        return False

def _build_ics(uid: str, summary: str, description: str,
               start_dt, end_dt,
               organiser_email: str, organiser_name: str,
               attendee_emails: list,
               location: str = "") -> str:
    """Build a minimal iCalendar (.ics) string usable as a Google Calendar invite."""
    import uuid as _uuid
    fmt       = "%Y%m%dT%H%M%SZ"
    now_str   = __import__("datetime").datetime.utcnow().strftime(fmt)
    start_str = start_dt.strftime(fmt)
    end_str   = end_dt.strftime(fmt)
    uid_val   = uid or str(_uuid.uuid4())

    location_line = f"LOCATION:{location}\r\n" if location else ""

    return (
        "BEGIN:VCALENDAR\r\n"
        "VERSION:2.0\r\n"
        "PRODID:-//SolaceSquad//Appointment//EN\r\n"
        "METHOD:PUBLISH\r\n"
        "BEGIN:VEVENT\r\n"
        f"UID:{uid_val}\r\n"
        f"DTSTAMP:{now_str}\r\n"
        f"DTSTART:{start_str}\r\n"
        f"DTEND:{end_str}\r\n"
        f"SUMMARY:{summary}\r\n"
        f"DESCRIPTION:{description}\r\n"
        f"ORGANIZER;CN={organiser_name}:mailto:{organiser_email}\r\n"
        + location_line +
        "STATUS:CONFIRMED\r\n"
        "SEQUENCE:0\r\n"
        "END:VEVENT\r\n"
        "END:VCALENDAR\r\n"
    )
def send_appointment_email(
    *,
    to_email: str,
    to_name: str,
    action: str,                   # "booked" | "cancelled"
    appointment_id: int,
    user_name: str,
    consultant_name: str,
    appointment_date,              # datetime (UTC)
    duration_minutes: int,
    notes: str = "",
    organiser_email: str = "",
    organiser_name: str  = "",
    attendee_emails: list = None,
    admin_booked: bool = False,
) -> bool:
    """
    Send a styled appointment confirmation or cancellation email.
    For bookings, a Google Calendar .ics invite is attached.
    """
    import base64 as _b64, datetime as _dt

    end_dt      = appointment_date + _dt.timedelta(minutes=duration_minutes)
    import timezone_utils
    local_dt = timezone_utils.to_local(appointment_date, "Asia/Kolkata")
    local_start = local_dt.strftime("%A, %B %d %Y at %I:%M %p IST")
    dur_label   = (f"{duration_minutes} min" if duration_minutes < 60
                   else f"{duration_minutes // 60}h"
                   + (f" {duration_minutes % 60}min" if duration_minutes % 60 else ""))

    is_booked    = (action == "booked")
    header_color = "#0f766e" if is_booked else "#dc2626"
    header_emoji = "📅" if is_booked else "❌"
    action_label = "Appointment Confirmed" if is_booked else "Appointment Cancelled"
    subject      = f"[SolaceSquad] {action_label} — {local_start}"

    join_block = ""
    join_text_line = ""
    join_url = ""
    if is_booked:
        app_base_url = "https://www.solacesquad.com"
        login_url = f"{app_base_url}/login"
        join_block = f"""
    <div style='background:#f0fdf4;border:1px solid #0d9488;border-radius:12px;
                padding:20px;margin:20px 0;text-align:center;'>
      <p style='margin:0 0 12px;font-size:15px;color:#111827;'><strong>Video Call Session Link</strong></p>
      <a href='{login_url}' style='background-color:#0d9488;color:#ffffff;padding:12px 24px;
                 border-radius:8px;text-decoration:none;font-weight:bold;display:inline-block;
                 box-shadow:0 4px 6px rgba(13,148,136,0.15);'>Login to the app to join the call</a>
      <p style='margin:10px 0 0;font-size:12px;color:#6b7280;'>
        Or copy and paste this link: <br>
        <a href='{login_url}' style='color:#0d9488;'>{login_url}</a>
      </p>
    </div>
"""
        join_text_line = f"Join Call Link: {login_url}\n"

    admin_notice_block = ""
    if is_booked and admin_booked:
        admin_notice_block = f"""
    <div style='background:#fffbeb;border:1px solid #f59e0b;border-radius:12px;
                padding:16px;margin:20px 0;color:#b45309;font-size:14px;'>
      ⚠️ <strong>Notice:</strong> This appointment was scheduled by an administrator on behalf of <strong>{user_name}</strong>.
    </div>
"""

    notes_block = (
        f"<p style='background:#f3f4f6;padding:12px;border-radius:8px;"
        f"font-size:14px;color:#374151;'><strong>Notes:</strong> {notes}</p>"
        if notes else ""
    )
    cal_notice = (
        "<p style='background:#ecfdf5;border-left:4px solid #10b981;"
        "padding:12px 16px;border-radius:4px;font-size:14px;color:#065f46;'>"
        "📎 A <strong>Google Calendar invite</strong> (.ics) is attached — "
        "open it to add this session directly to your calendar.</p>"
        if is_booked else ""
    )

    html = f"""<!DOCTYPE html><html><head><meta charset='utf-8'></head>
<body style='font-family:-apple-system,BlinkMacSystemFont,Segoe UI,Roboto,sans-serif;
background:#f3f4f6;margin:0;padding:24px;'>
<div style='max-width:580px;margin:0 auto;background:#fff;border-radius:16px;
overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,.1);'>
  <div style='background:{header_color};padding:32px 28px;text-align:center;color:#fff;'>
    <div style='font-size:3rem;margin-bottom:8px;'>{header_emoji}</div>
    <h1 style='margin:0;font-size:1.5rem;font-weight:700;'>{action_label}</h1>
    <p style='margin:6px 0 0;font-size:.875rem;opacity:.85;'>SolaceSquad Wellness Platform</p>
  </div>
  <div style='padding:28px;'>
    <p style='font-size:16px;color:#111827;margin-top:0;'>Hi <strong>{to_name}</strong>,</p>
    <p style='color:#374151;'>
      {"Your appointment has been <strong>successfully booked</strong>." if is_booked
       else "Your appointment has been <strong>cancelled</strong>."}
    </p>
    {admin_notice_block}
    <div style='background:#f0fdf4;border:1px solid #bbf7d0;border-radius:12px;
                padding:20px;margin:20px 0;'>
      <table style='width:100%;border-collapse:collapse;font-size:14px;color:#374151;'>
        <tr><td style='padding:6px 0;color:#6b7280;width:38%;'>👤 User</td>
            <td><strong>{user_name}</strong></td></tr>
        <tr><td style='padding:6px 0;color:#6b7280;'>🩺 Consultant</td>
            <td><strong>{consultant_name}</strong></td></tr>
        <tr><td style='padding:6px 0;color:#6b7280;'>🗓️ Date &amp; Time</td>
            <td><strong>{local_start}</strong></td></tr>
        <tr><td style='padding:6px 0;color:#6b7280;'>⏱️ Duration</td>
            <td><strong>{dur_label}</strong></td></tr>
        <tr><td style='padding:6px 0;color:#6b7280;'>🔖 Ref ID</td>
            <td style='color:#9ca3af;'>#{appointment_id}</td></tr>
      </table>
    </div>
    {join_block}
    {notes_block}
    {cal_notice}
    <p style='color:#6b7280;font-size:13px;margin-top:24px;'>
      Questions? Visit your dashboard or reply to this email.<br>
      <em>— The SolaceSquad Team</em>
    </p>
  </div>
  <div style='background:#f9fafb;padding:16px;text-align:center;
              font-size:12px;color:#9ca3af;border-top:1px solid #e5e7eb;'>
    © 2026 SolaceSquad. All rights reserved.
  </div>
</div>
</body></html>"""

    text = (
        f"Hi {to_name},\n\n"
        f"{action_label}\n\n"
        f"User:        {user_name}\n"
        f"Consultant:  {consultant_name}\n"
        f"Date & Time: {local_start}\n"
        f"Duration:    {dur_label}\n"
        f"Ref ID:      #{appointment_id}\n"
        + join_text_line
        + (f"Notes:       {notes}\n" if notes else "")
        + "\n— The SolaceSquad Team\n"
    )

    # .ics calendar attachment (bookings only)
    attachments = []
    if is_booked:
        ics_str = _build_ics(
            uid             = f"appt-{appointment_id}@solacesquad.com",
            summary         = f"SolaceSquad: {user_name} ↔ {consultant_name}",
            description     = (f"Appointment #{appointment_id}\\nDuration: {dur_label}"
                               + (f"\\nJoin Call Link: {join_url}" if join_url else "")
                               + (f"\\nNotes: {notes}" if notes else "")),
            start_dt        = appointment_date,
            end_dt          = end_dt,
            organiser_email = "noreply@solacesquad.com",
            organiser_name  = "SolaceSquad",
            attendee_emails = attendee_emails or [],
            location        = join_url,
        )
        ics_b64 = _b64.b64encode(ics_str.encode("utf-8")).decode("utf-8")
        attachments.append({
            "content":     ics_b64,
            "type":        "text/calendar; method=REQUEST",
            "filename":    "appointment.ics",
            "disposition": "attachment",
        })

    return _send_raw_appt(to_email, subject, html, text, attachments or None)


# ──────────────────────────────────────────────────────────────────────────────
# Email OTP  (sent at signup for email address verification)
# ──────────────────────────────────────────────────────────────────────────────

def send_email_otp(to_email: str, user_name: str, otp_code: str) -> bool:
    """Send a 6-digit OTP to verify the user's email during signup."""
    subject = "Your SolaceSquad Verification Code"
    html = f"""<!DOCTYPE html><html><head><meta charset="utf-8"></head>
<body style="font-family:-apple-system,BlinkMacSystemFont,Segoe UI,Roboto,sans-serif;
background:#f3f4f6;margin:0;padding:24px;">
<div style="max-width:520px;margin:0 auto;background:#fff;border-radius:16px;
overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,.1);">
  <div style="background:linear-gradient(135deg,#0f766e,#0d9488);padding:32px 28px;
  text-align:center;color:#fff;">
    <div style="font-size:2.5rem;margin-bottom:8px;">🔐</div>
    <h1 style="margin:0;font-size:1.4rem;font-weight:700;">Verify Your Email</h1>
    <p style="margin:6px 0 0;opacity:.85;font-size:.875rem;">SolaceSquad Signup Verification</p>
  </div>
  <div style="padding:32px 28px;">
    <p style="color:#111827;margin-top:0;">Hi <strong>{user_name}</strong>,</p>
    <p style="color:#374151;">Use the code below to verify your email address. It expires in <strong>10 minutes</strong>.</p>
    <div style="background:#f0fdf4;border:2px solid #10b981;border-radius:12px;
    text-align:center;padding:24px;margin:24px 0;">
      <div style="font-size:2.5rem;font-weight:800;letter-spacing:0.35em;
      color:#0f766e;font-family:monospace;">{otp_code}</div>
    </div>
    <p style="color:#6b7280;font-size:13px;">If you didn't request this, please ignore this email.<br>
    <em>— The SolaceSquad Team</em></p>
  </div>
  <div style="background:#f9fafb;padding:16px;text-align:center;
  font-size:12px;color:#9ca3af;border-top:1px solid #e5e7eb;">
    © 2026 SolaceSquad. All rights reserved.
  </div>
</div></body></html>"""
    text = f"Hi {user_name},\n\nYour SolaceSquad verification code is: {otp_code}\n\nIt expires in 10 minutes.\n\n— The SolaceSquad Team"
    return _send_raw_appt(to_email, subject, html, text)


# ──────────────────────────────────────────────────────────────────────────────
# Consultant Approval Email  (sent by admin when approving a consultant)
# ──────────────────────────────────────────────────────────────────────────────

def send_consultant_approval_email(to_email: str, consultant_name: str) -> bool:
    """Notify a consultant that their account has been approved by admin."""
    subject = "🎉 You're Approved — Welcome to SolaceSquad!"
    login_url = os.getenv("APP_BASE_URL", "https://solacesquad.in") + "/login"
    html = f"""<!DOCTYPE html><html><head><meta charset="utf-8"></head>
<body style="font-family:-apple-system,BlinkMacSystemFont,Segoe UI,Roboto,sans-serif;
background:#f3f4f6;margin:0;padding:24px;">
<div style="max-width:520px;margin:0 auto;background:#fff;border-radius:16px;
overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,.1);">
  <div style="background:linear-gradient(135deg,#0f766e,#0d9488);padding:32px 28px;
  text-align:center;color:#fff;">
    <div style="font-size:2.5rem;margin-bottom:8px;">✅</div>
    <h1 style="margin:0;font-size:1.4rem;font-weight:700;">Application Approved!</h1>
    <p style="margin:6px 0 0;opacity:.85;font-size:.875rem;">SolaceSquad Consultant Platform</p>
  </div>
  <div style="padding:32px 28px;">
    <p style="color:#111827;margin-top:0;">Hi <strong>{consultant_name}</strong>,</p>
    <p style="color:#374151;">Great news! Your consultant application has been <strong>reviewed and approved</strong>
    by our admin team. You can now log in and start your journey with SolaceSquad.</p>
    <div style="text-align:center;margin:28px 0;">
      <a href="{login_url}" style="display:inline-block;background:linear-gradient(135deg,#0f766e,#0d9488);
      color:#fff;padding:14px 32px;border-radius:8px;text-decoration:none;
      font-weight:700;font-size:16px;">Log In to Your Dashboard →</a>
    </div>
    <p style="color:#6b7280;font-size:13px;">
      If the button doesn't work, copy this link: <a href="{login_url}">{login_url}</a><br><br>
      <em>— The SolaceSquad Team</em>
    </p>
  </div>
  <div style="background:#f9fafb;padding:16px;text-align:center;
  font-size:12px;color:#9ca3af;border-top:1px solid #e5e7eb;">
    © 2026 SolaceSquad. All rights reserved.
  </div>
</div></body></html>"""
    text = (f"Hi {consultant_name},\n\nCongratulations! Your SolaceSquad consultant application has been approved.\n\n"
            f"Log in here: {login_url}\n\n— The SolaceSquad Team")
    return _send_raw_appt(to_email, subject, html, text)


# ──────────────────────────────────────────────────────────────────────────────
# Admin Alert  (sent to admin when new consultant submits onboarding form)
# ──────────────────────────────────────────────────────────────────────────────

def send_admin_new_consultant_alert(admin_email: str, consultant_name: str,
                                     consultant_email: str) -> bool:
    """Alert admin that a new consultant has submitted their onboarding questionnaire."""
    subject = f"[SolaceSquad] New Consultant Application — {consultant_name}"
    admin_url = os.getenv("APP_BASE_URL", "https://solacesquad.in") + "/admin/consultants"
    html = f"""<!DOCTYPE html><html><head><meta charset="utf-8"></head>
<body style="font-family:-apple-system,BlinkMacSystemFont,Segoe UI,Roboto,sans-serif;
background:#f3f4f6;margin:0;padding:24px;">
<div style="max-width:520px;margin:0 auto;background:#fff;border-radius:16px;
overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,.1);">
  <div style="background:linear-gradient(135deg,#1d4ed8,#3b82f6);padding:28px;
  text-align:center;color:#fff;">
    <div style="font-size:2rem;margin-bottom:8px;">🧑‍⚕️</div>
    <h1 style="margin:0;font-size:1.3rem;font-weight:700;">New Consultant Application</h1>
  </div>
  <div style="padding:28px;">
    <p style="color:#111827;margin-top:0;">A new consultant has submitted their onboarding form and is waiting for approval.</p>
    <table style="width:100%;border-collapse:collapse;font-size:14px;color:#374151;margin:16px 0;">
      <tr><td style="padding:8px 0;color:#6b7280;width:35%;">Name</td><td><strong>{consultant_name}</strong></td></tr>
      <tr><td style="padding:8px 0;color:#6b7280;">Email</td><td>{consultant_email}</td></tr>
    </table>
    <div style="text-align:center;margin:20px 0;">
      <a href="{admin_url}" style="display:inline-block;background:linear-gradient(135deg,#1d4ed8,#3b82f6);
      color:#fff;padding:12px 28px;border-radius:8px;text-decoration:none;font-weight:700;">
      Review &amp; Approve →</a>
    </div>
  </div>
  <div style="background:#f9fafb;padding:14px;text-align:center;
  font-size:12px;color:#9ca3af;border-top:1px solid #e5e7eb;">
    © 2026 SolaceSquad Admin
  </div>
</div></body></html>"""
    text = (f"New consultant application from {consultant_name} ({consultant_email}).\n\n"
            f"Review at: {admin_url}")
    return _send_raw_appt(admin_email, subject, html, text)


def send_plain_email(to_email: str, subject: str, body: str) -> bool:
    """Send a plain-text email (generic helper for notifications)."""
    try:
        api_key = os.getenv("SENDGRID_API_KEY", "").strip()
        from_email_addr = os.getenv("FROM_EMAIL", "noreply@solacesquad.com")
        if not api_key:
            print("[EMAIL] SENDGRID_API_KEY not set — skipping plain email")
            return False
        message = Mail(
            from_email=Email(from_email_addr),
            to_emails=To(to_email),
            subject=subject,
            plain_text_content=Content("text/plain", body),
        )
        sg = SendGridAPIClient(api_key)
        resp = sg.send(message)
        return resp.status_code in (200, 201, 202)
    except Exception as e:
        print(f"[EMAIL] send_plain_email error: {e}")
        return False



# ──────────────────────────────────────────────────────────────────────────────
# Admin Assistant Alert Emails
# ──────────────────────────────────────────────────────────────────────────────

def send_admin_assistant_form_saved_alert(
    admin_email: str,
    consultant_name: str,
    consultant_email: str,
    assistant_name: str,
    profile_id: int,
) -> bool:
    """Alert admin that an assistant has filled & saved a consultant onboarding form."""
    base_url = os.getenv("APP_BASE_URL", "https://solacesquad.in")
    review_url = f"{base_url}/admin/consultant/{profile_id}"
    subject = f"[SolaceSquad] Onboarding Form Updated — {consultant_name}"
    html = f"""<!DOCTYPE html><html><head><meta charset="utf-8"></head>
<body style="font-family:-apple-system,BlinkMacSystemFont,Segoe UI,Roboto,sans-serif;
background:#f3f4f6;margin:0;padding:24px;">
<div style="max-width:520px;margin:0 auto;background:#fff;border-radius:16px;
overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,.1);">
  <div style="background:linear-gradient(135deg,#0d9488,#0f766e);padding:28px;
  text-align:center;color:#fff;">
    <div style="font-size:2rem;margin-bottom:8px;">📋</div>
    <h1 style="margin:0;font-size:1.3rem;font-weight:700;">Onboarding Form Updated by Assistant</h1>
  </div>
  <div style="padding:28px;">
    <p style="color:#111827;margin-top:0;">
      Admin Assistant <strong>{assistant_name}</strong> has filled and saved a consultant onboarding form on behalf of the applicant below.
      The form is <strong>awaiting your approval</strong>.
    </p>
    <table style="width:100%;border-collapse:collapse;font-size:14px;color:#374151;margin:16px 0;">
      <tr><td style="padding:8px 0;color:#6b7280;width:35%;">Consultant</td><td><strong>{consultant_name}</strong></td></tr>
      <tr><td style="padding:8px 0;color:#6b7280;">Email</td><td>{consultant_email}</td></tr>
      <tr><td style="padding:8px 0;color:#6b7280;">Filled by</td><td>{assistant_name} (Assistant)</td></tr>
    </table>
    <div style="text-align:center;margin:20px 0;">
      <a href="{review_url}" style="display:inline-block;background:linear-gradient(135deg,#0d9488,#0f766e);
      color:#fff;padding:12px 28px;border-radius:8px;text-decoration:none;font-weight:700;">
      Review &amp; Approve →</a>
    </div>
  </div>
  <div style="background:#f9fafb;padding:14px;text-align:center;
  font-size:12px;color:#9ca3af;border-top:1px solid #e5e7eb;">
    © 2026 SolaceSquad Admin
  </div>
</div></body></html>"""
    text = (
        f"Assistant {assistant_name} has filled the onboarding form for {consultant_name} ({consultant_email}).\n\n"
        f"Review and approve at: {review_url}"
    )
    return _send_raw_appt(admin_email, subject, html, text)


def send_admin_assistant_blog_saved_alert(
    admin_email: str,
    blog_title: str,
    assistant_name: str,
    blog_id: int,
) -> bool:
    """Alert admin that an assistant has saved a new blog draft pending publish."""
    base_url = os.getenv("APP_BASE_URL", "https://solacesquad.in")
    review_url = f"{base_url}/admin/blogs"
    subject = f"[SolaceSquad] New Blog Draft Ready — \"{blog_title}\""
    html = f"""<!DOCTYPE html><html><head><meta charset="utf-8"></head>
<body style="font-family:-apple-system,BlinkMacSystemFont,Segoe UI,Roboto,sans-serif;
background:#f3f4f6;margin:0;padding:24px;">
<div style="max-width:520px;margin:0 auto;background:#fff;border-radius:16px;
overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,.1);">
  <div style="background:linear-gradient(135deg,#7c3aed,#6d28d9);padding:28px;
  text-align:center;color:#fff;">
    <div style="font-size:2rem;margin-bottom:8px;">✍️</div>
    <h1 style="margin:0;font-size:1.3rem;font-weight:700;">New Blog Draft Saved</h1>
  </div>
  <div style="padding:28px;">
    <p style="color:#111827;margin-top:0;">
      Admin Assistant <strong>{assistant_name}</strong> has written and saved a new blog draft.
      It is <strong>waiting for your review and publish approval</strong>.
    </p>
    <table style="width:100%;border-collapse:collapse;font-size:14px;color:#374151;margin:16px 0;">
      <tr><td style="padding:8px 0;color:#6b7280;width:35%;">Blog Title</td><td><strong>{blog_title}</strong></td></tr>
      <tr><td style="padding:8px 0;color:#6b7280;">Written by</td><td>{assistant_name} (Assistant)</td></tr>
      <tr><td style="padding:8px 0;color:#6b7280;">Status</td><td><span style="color:#d97706;font-weight:600;">Draft — Not Published</span></td></tr>
    </table>
    <div style="text-align:center;margin:20px 0;">
      <a href="{review_url}" style="display:inline-block;background:linear-gradient(135deg,#7c3aed,#6d28d9);
      color:#fff;padding:12px 28px;border-radius:8px;text-decoration:none;font-weight:700;">
      Review &amp; Publish →</a>
    </div>
  </div>
  <div style="background:#f9fafb;padding:14px;text-align:center;
  font-size:12px;color:#9ca3af;border-top:1px solid #e5e7eb;">
    © 2026 SolaceSquad Admin
  </div>
</div></body></html>"""
    text = (
        f"Assistant {assistant_name} has saved a new blog draft: \"{blog_title}\".\n\n"
        f"Review and publish at: {review_url}"
    )
    return _send_raw_appt(admin_email, subject, html, text)


# ──────────────────────────────────────────────────────────────────────────────
# Auto-Renewal Email Notifications
# ──────────────────────────────────────────────────────────────────────────────

def send_renewal_reminder_email(
    to_email: str,
    user_name: str,
    plan_name: str,
    amount: float,
    renewal_date: str,  # formatted string e.g. "4 July 2026"
) -> bool:
    """Send a renewal reminder email 1 day before the auto-renewal charge."""
    base_url = os.getenv("APP_BASE_URL", "https://solacesquad.in")
    manage_url = base_url + "/app/plans"
    subject = f"Your SolaceSquad plan renews tomorrow 🔔"
    html = f"""<!DOCTYPE html><html><head><meta charset="utf-8"></head>
<body style="font-family:-apple-system,BlinkMacSystemFont,Segoe UI,Roboto,sans-serif;
background:#f3f4f6;margin:0;padding:24px;">
<div style="max-width:520px;margin:0 auto;background:#fff;border-radius:16px;
overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,.1);">
  <div style="background:linear-gradient(135deg,#0f766e,#0d9488);padding:32px 28px;
  text-align:center;color:#fff;">
    <div style="font-size:2.5rem;margin-bottom:8px;">🔔</div>
    <h1 style="margin:0;font-size:1.4rem;font-weight:700;">Plan Renewing Tomorrow</h1>
    <p style="margin:6px 0 0;opacity:.85;font-size:.875rem;">SolaceSquad Subscription</p>
  </div>
  <div style="padding:32px 28px;">
    <p style="color:#111827;margin-top:0;">Hi <strong>{user_name}</strong>,</p>
    <p style="color:#374151;">Just a heads-up — your <strong>{plan_name}</strong> plan will automatically renew tomorrow.</p>
    <div style="background:#f0fdf4;border:1px solid #6ee7b7;border-radius:12px;padding:20px;margin:20px 0;">
      <table style="width:100%;border-collapse:collapse;font-size:15px;">
        <tr><td style="padding:6px 0;color:#6b7280;width:45%;">Plan</td>
            <td><strong>{plan_name}</strong></td></tr>
        <tr><td style="padding:6px 0;color:#6b7280;">Amount</td>
            <td><strong>&#8377;{amount:,.0f}</strong></td></tr>
        <tr><td style="padding:6px 0;color:#6b7280;">Renewal Date</td>
            <td><strong>{renewal_date}</strong></td></tr>
      </table>
    </div>
    <div style="text-align:center;margin:24px 0;">
      <a href="{manage_url}" style="display:inline-block;background:linear-gradient(135deg,#0f766e,#0d9488);
      color:#fff;padding:14px 28px;border-radius:8px;text-decoration:none;font-weight:700;font-size:15px;">
        Manage Subscription &rarr;
      </a>
    </div>
    <p style="color:#9ca3af;font-size:12px;text-align:center;">
      To cancel auto-renewal, visit your plan settings before midnight tonight.<br>
      <em>— The SolaceSquad Team</em>
    </p>
  </div>
  <div style="background:#f9fafb;padding:16px;text-align:center;
font-size:12px;color:#9ca3af;border-top:1px solid #e5e7eb;">
    &copy; 2026 SolaceSquad. All rights reserved.
  </div>
</div></body></html>"""
    text = (
        f"Hi {user_name},\n\nYour {plan_name} plan renews tomorrow ({renewal_date}) for "
        f"\u20b9{amount:,.0f}.\n\nTo manage your subscription, visit: {manage_url}\n\n"
        f"\u2014 The SolaceSquad Team"
    )
    print(f"[AUTO-RENEW] Sending renewal reminder to {to_email} for plan '{plan_name}'")
    return _send_raw_appt(to_email, subject, html, text)


def send_payment_receipt_email(
    to_email: str,
    user_name: str,
    plan_name: str,
    amount: float,
    invoice_number: str,
    next_renewal_date: str,  # formatted string e.g. "4 August 2026"
) -> bool:
    """Send a payment receipt after a successful auto-renewal charge."""
    base_url = os.getenv("APP_BASE_URL", "https://solacesquad.in")
    billing_url = base_url + "/app/billing"
    subject = "Payment successful \u2014 SolaceSquad \u2705"
    html = f"""<!DOCTYPE html><html><head><meta charset="utf-8"></head>
<body style="font-family:-apple-system,BlinkMacSystemFont,Segoe UI,Roboto,sans-serif;
background:#f3f4f6;margin:0;padding:24px;">
<div style="max-width:520px;margin:0 auto;background:#fff;border-radius:16px;
overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,.1);">
  <div style="background:linear-gradient(135deg,#059669,#10b981);padding:32px 28px;
  text-align:center;color:#fff;">
    <div style="font-size:2.5rem;margin-bottom:8px;">&#10003;</div>
    <h1 style="margin:0;font-size:1.4rem;font-weight:700;">Payment Successful</h1>
    <p style="margin:6px 0 0;opacity:.85;font-size:.875rem;">SolaceSquad Auto-Renewal Receipt</p>
  </div>
  <div style="padding:32px 28px;">
    <p style="color:#111827;margin-top:0;">Hi <strong>{user_name}</strong>,</p>
    <p style="color:#374151;">Your subscription has been renewed successfully. Here's your receipt:</p>
    <div style="background:#f0fdf4;border:1px solid #6ee7b7;border-radius:12px;padding:20px;margin:20px 0;">
      <table style="width:100%;border-collapse:collapse;font-size:15px;">
        <tr><td style="padding:6px 0;color:#6b7280;width:45%;">Invoice #</td>
            <td><strong>{invoice_number}</strong></td></tr>
        <tr><td style="padding:6px 0;color:#6b7280;">Plan</td>
            <td><strong>{plan_name}</strong></td></tr>
        <tr><td style="padding:6px 0;color:#6b7280;">Amount Paid</td>
            <td><strong style="color:#059669;">&#8377;{amount:,.0f}</strong></td></tr>
        <tr><td style="padding:6px 0;color:#6b7280;">Next Renewal</td>
            <td><strong>{next_renewal_date}</strong></td></tr>
      </table>
    </div>
    <div style="text-align:center;margin:24px 0;">
      <a href="{billing_url}" style="display:inline-block;background:linear-gradient(135deg,#059669,#10b981);
      color:#fff;padding:12px 24px;border-radius:8px;text-decoration:none;font-weight:700;font-size:14px;">
        View Invoice &rarr;
      </a>
    </div>
    <p style="color:#9ca3af;font-size:12px;text-align:center;">
      Thank you for being a SolaceSquad member!<br>
      <em>— The SolaceSquad Team</em>
    </p>
  </div>
  <div style="background:#f9fafb;padding:16px;text-align:center;
font-size:12px;color:#9ca3af;border-top:1px solid #e5e7eb;">
    &copy; 2026 SolaceSquad. All rights reserved.
  </div>
</div></body></html>"""
    text = (
        f"Hi {user_name},\n\nYour {plan_name} subscription has been renewed.\n\n"
        f"Invoice: {invoice_number}\nAmount: \u20b9{amount:,.0f}\nNext renewal: {next_renewal_date}\n\n"
        f"View invoice: {billing_url}\n\n\u2014 The SolaceSquad Team"
    )
    print(f"[AUTO-RENEW] Sending payment receipt to {to_email} | invoice={invoice_number}")
    return _send_raw_appt(to_email, subject, html, text)


def send_renewal_failed_email(
    to_email: str,
    user_name: str,
    plan_name: str,
    grace_period_ends: str,   # formatted date string (used when is_final_notice=False)
    is_final_notice: bool = False,
) -> bool:
    """
    Send a payment failure email.
    First failure (is_final_notice=False): explains 3-day grace period.
    Final notice (is_final_notice=True): confirms downgrade to Free.
    """
    base_url = os.getenv("APP_BASE_URL", "https://solacesquad.in")
    plans_url = base_url + "/app/plans"

    if is_final_notice:
        subject = "Your plan has been downgraded to Free \u2014 SolaceSquad"
        header_color = "#dc2626"
        header_emoji = "&#9888;"
        header_title = "Plan Downgraded"
        body_html = f"""
    <p style="color:#374151;">We were unable to process your payment for the <strong>{plan_name}</strong> plan.
    Your account has been downgraded to the <strong>Free plan</strong>.</p>
    <p style="color:#374151;">To restore your {plan_name} plan and all its features, please re-subscribe:</p>
    <div style="text-align:center;margin:24px 0;">
      <a href="{plans_url}" style="display:inline-block;background:linear-gradient(135deg,#dc2626,#b91c1c);
      color:#fff;padding:14px 28px;border-radius:8px;text-decoration:none;font-weight:700;font-size:15px;">
        Re-subscribe Now &rarr;
      </a>
    </div>"""
        text_body = (
            f"We were unable to charge your {plan_name} plan. Your account has been downgraded to Free.\n\n"
            f"To re-subscribe, visit: {plans_url}"
        )
    else:
        subject = "Payment failed \u2014 3-day grace period started \u26a0\ufe0f"
        header_color = "#d97706"
        header_emoji = "&#9888;"
        header_title = "Payment Failed"
        body_html = f"""
    <p style="color:#374151;">We were unable to automatically renew your <strong>{plan_name}</strong> plan.</p>
    <div style="background:#fef3c7;border-left:4px solid #f59e0b;padding:16px;border-radius:4px;margin:20px 0;">
      <strong>Grace Period Active</strong><br>
      Your plan access continues until <strong>{grace_period_ends}</strong>. If payment is not received
      by then, your account will be downgraded to the Free plan.
    </div>
    <p style="color:#374151;">To keep your plan, please re-subscribe before {grace_period_ends}:</p>
    <div style="text-align:center;margin:24px 0;">
      <a href="{plans_url}" style="display:inline-block;background:linear-gradient(135deg,#d97706,#b45309);
      color:#fff;padding:14px 28px;border-radius:8px;text-decoration:none;font-weight:700;font-size:15px;">
        Re-subscribe Now &rarr;
      </a>
    </div>"""
        text_body = (
            f"Payment failed for your {plan_name} plan.\n\n"
            f"Grace period: your access continues until {grace_period_ends}.\n"
            f"After that, your account will be downgraded to Free.\n\n"
            f"To re-subscribe: {plans_url}"
        )

    html = f"""<!DOCTYPE html><html><head><meta charset="utf-8"></head>
<body style="font-family:-apple-system,BlinkMacSystemFont,Segoe UI,Roboto,sans-serif;
background:#f3f4f6;margin:0;padding:24px;">
<div style="max-width:520px;margin:0 auto;background:#fff;border-radius:16px;
overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,.1);">
  <div style="background:{header_color};padding:32px 28px;
  text-align:center;color:#fff;">
    <div style="font-size:2.5rem;margin-bottom:8px;">{header_emoji}</div>
    <h1 style="margin:0;font-size:1.4rem;font-weight:700;">{header_title}</h1>
    <p style="margin:6px 0 0;opacity:.85;font-size:.875rem;">SolaceSquad Subscription</p>
  </div>
  <div style="padding:32px 28px;">
    <p style="color:#111827;margin-top:0;">Hi <strong>{user_name}</strong>,</p>
    {body_html}
    <p style="color:#9ca3af;font-size:12px;text-align:center;margin-top:24px;">
      Questions? Contact us at support@solacesquad.com<br>
      <em>— The SolaceSquad Team</em>
    </p>
  </div>
  <div style="background:#f9fafb;padding:16px;text-align:center;
font-size:12px;color:#9ca3af;border-top:1px solid #e5e7eb;">
    &copy; 2026 SolaceSquad. All rights reserved.
  </div>
</div></body></html>"""
    text = f"Hi {user_name},\n\n{text_body}\n\n\u2014 The SolaceSquad Team"
    print(f"[AUTO-RENEW] Sending renewal-failed email to {to_email} | final={is_final_notice}")
    return _send_raw_appt(to_email, subject, html, text)


def send_payment_invoice_email(
    to_email: str,
    user_name: str,
    invoice_number: str,
    description: str,
    amount: float,
    payment_id: str = None,
    txn_type: str = None,
    related_entity_type: str = None,
    related_entity_id: int = None,
    user_id: int = None,
    db_session = None,
) -> bool:
    """Send a detailed tax invoice email showing pre-GST subtotal, itemized discounts, 18% GST, and total paid."""
    try:
        sendgrid_api_key = os.getenv("SENDGRID_API_KEY")
        from_email = os.getenv("FROM_EMAIL", "noreply@solacesquad.com")
        if not sendgrid_api_key:
            print(f"[SendGrid] No API key — generic invoice would be sent to {to_email}")
            return False

        from datetime import datetime
        date_str = datetime.utcnow().strftime("%d %B %Y")
        base_url = os.getenv("APP_BASE_URL", "https://www.solacesquad.com")
        base_url = base_url.rstrip("/")
        logo_url = f"{base_url}/static/images/logo.png"

        subject = f"Invoice {invoice_number} for your payment to SolaceSquad ✅"
        
        # Default calculations
        item_cost = amount / 1.18
        plan_discount = 0.0
        blue_discount = 0.0
        prorate_discount = 0.0
        cost_after_discount = amount / 1.18
        gst_amount = amount - cost_after_discount
        total_paid = amount

        if db_session and related_entity_type and related_entity_id:
            try:
                from models import UserSubscription, UsagePlan, Appointment, FeatureUsageTopUp, PlanFeatureCap
                
                if related_entity_type == "subscription":
                    sub = db_session.query(UserSubscription).filter(UserSubscription.id == related_entity_id).first()
                    if sub and sub.plan:
                        plan = sub.plan
                        # Plan Discount
                        if plan.original_price and plan.original_price > plan.price:
                            plan_discount = plan.original_price - plan.price
                            item_cost = plan.original_price
                        else:
                            item_cost = plan.price
                        
                        # Prorated Discount
                        pre_tax_paid = amount / 1.18
                        calc_prorate = plan.price - pre_tax_paid
                        if calc_prorate > 0.05:
                            prorate_discount = round(calc_prorate, 2)
                        
                        cost_after_discount = pre_tax_paid
                        gst_amount = amount - cost_after_discount

                elif related_entity_type == "appointment":
                    appt = db_session.query(Appointment).filter(Appointment.id == related_entity_id).first()
                    if appt and appt.consultant:
                        profile = appt.consultant
                        fee = profile.consultation_fee or 0.0
                        duration = appt.duration_minutes or 60
                        
                        # Full cost without any waivers/discounts
                        full_cost = fee * (duration / 60)
                        item_cost = full_cost
                        
                        # Reconstruct first consultation waiver if applicable
                        created_at_limit = appt.created_at or datetime.utcnow()
                        prior_appts = db_session.query(Appointment).filter(
                            Appointment.user_id == user_id,
                            Appointment.status != "cancelled",
                            Appointment.created_at < created_at_limit
                        ).count()
                        is_first = (prior_appts == 0)
                        
                        chargeable_duration = max(0, duration - 30) if is_first else duration
                        fee_after_waiver = fee * (chargeable_duration / 60)
                        first_waiver = full_cost - fee_after_waiver
                        
                        # Blue plan discount (25%)
                        pre_tax_paid = amount / 1.18
                        calc_blue_discount = fee_after_waiver - pre_tax_paid
                        
                        if calc_blue_discount > 0.05:
                            blue_discount = round(calc_blue_discount, 2)
                        
                        if first_waiver > 0.05:
                            prorate_discount = round(first_waiver, 2)
                            
                        cost_after_discount = pre_tax_paid
                        gst_amount = amount - cost_after_discount

                elif related_entity_type in ("top_up", "feature_top_up"):
                    topup = db_session.query(FeatureUsageTopUp).filter(FeatureUsageTopUp.id == related_entity_id).first()
                    if topup:
                        original_price = 0.0
                        if topup.feature_key == "ai_chat" and topup.month_key == "lifetime":
                            if topup.quota_added == 5000:
                                original_price = 500.0
                            elif topup.quota_added == 25000:
                                original_price = 2000.0
                            elif topup.quota_added == 100000:
                                original_price = 5000.0
                        else:
                            # Other top-up or standard top-up
                            sub = db_session.query(UserSubscription).filter(
                                UserSubscription.user_id == user_id,
                                UserSubscription.status == "active"
                            ).first()
                            if sub:
                                cap = db_session.query(PlanFeatureCap).filter(
                                    PlanFeatureCap.plan_id == sub.plan_id,
                                    PlanFeatureCap.feature_key == topup.feature_key
                                ).first()
                                if cap:
                                    original_price = cap.extend_price
                        
                        if original_price > 0:
                            item_cost = original_price
                            pre_tax_paid = amount / 1.18
                            # Blue plan discount (25%)
                            calc_blue_discount = original_price - pre_tax_paid
                            if calc_blue_discount > 0.05:
                                blue_discount = round(calc_blue_discount, 2)
                            
                            cost_after_discount = pre_tax_paid
                            gst_amount = amount - cost_after_discount
            except Exception as _calc_err:
                print(f"[WARN] Error calculating invoice itemized details: {_calc_err}")

        # Construct discount rows
        plan_discount_row = f"""
        <tr style="color: {'#16a34a' if plan_discount > 0 else '#9ca3af'}; font-size: 14px;">
            <td style="padding: 8px 0; padding-left: 15px;">&emsp;↳ 1. Plan Discount{' (75% off Blue Plan)' if (plan_discount > 0 and 'blue' in description.lower()) else ''}</td>
            <td style="padding: 8px 0; text-align: right;">{f'-₹{plan_discount:,.2f}' if plan_discount > 0 else '₹0.00'}</td>
        </tr>
        """
        
        blue_discount_row = f"""
        <tr style="color: {'#16a34a' if blue_discount > 0 else '#9ca3af'}; font-size: 14px;">
            <td style="padding: 8px 0; padding-left: 15px;">&emsp;↳ 2. Blue Plan Member Discount (25% off Consultation & Emora)</td>
            <td style="padding: 8px 0; text-align: right;">{f'-₹{blue_discount:,.2f}' if blue_discount > 0 else '₹0.00'}</td>
        </tr>
        """
        
        prorate_discount_row = f"""
        <tr style="color: {'#16a34a' if prorate_discount > 0 else '#9ca3af'}; font-size: 14px;">
            <td style="padding: 8px 0; padding-left: 15px;">&emsp;↳ 3. Prorated Plan Switch / Waiver Discount</td>
            <td style="padding: 8px 0; text-align: right;">{f'-₹{prorate_discount:,.2f}' if prorate_discount > 0 else '₹0.00'}</td>
        </tr>
        """

        html_content = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
            line-height: 1.6;
            color: #374151;
            background-color: #f3f4f6;
            margin: 0;
            padding: 0;
        }}
        .email-container {{
            max-width: 600px;
            margin: 40px auto;
            background: #ffffff;
            border-radius: 16px;
            overflow: hidden;
            box-shadow: 0 10px 25px rgba(0, 0, 0, 0.05);
            border: 1px solid #e5e7eb;
        }}
        .letterhead {{
            background: #ffffff;
            border-bottom: 3px solid #0d9488;
            padding: 30px 40px;
            text-align: center;
        }}
        .logo {{
            height: 50px;
            width: auto;
            display: inline-block;
        }}
        .invoice-body {{
            padding: 40px;
        }}
        .invoice-title {{
            font-size: 24px;
            font-weight: 800;
            color: #111827;
            margin: 0 0 10px;
            letter-spacing: -0.02em;
        }}
        .meta-grid {{
            display: table;
            width: 100%;
            margin-top: 20px;
            border-top: 1px solid #f3f4f6;
            padding-top: 20px;
        }}
        .meta-col {{
            display: table-cell;
            width: 50%;
            font-size: 13px;
            color: #6b7280;
            vertical-align: top;
        }}
        .invoice-table {{
            width: 100%;
            border-collapse: collapse;
            margin: 30px 0 20px;
        }}
        .invoice-table th {{
            font-size: 12px;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: #9ca3af;
            border-bottom: 2px solid #f3f4f6;
            padding: 10px 0;
            text-align: left;
        }}
        .invoice-table td {{
            padding: 12px 0;
            border-bottom: 1px solid #f9fafb;
            font-size: 14px;
        }}
        .totals-section {{
            margin-top: 30px;
            padding-top: 20px;
            border-top: 2px dashed #e5e7eb;
        }}
        .totals-row {{
            margin: 8px 0;
            font-size: 14px;
            color: #4b5563;
        }}
        .totals-row.total {{
            font-size: 18px;
            font-weight: 800;
            color: #111827;
            border-top: 1px solid #e5e7eb;
            padding-top: 15px;
            margin-top: 12px;
        }}
        .footer {{
            text-align: center;
            padding: 30px 40px;
            background: #f9fafb;
            border-top: 1px solid #e5e7eb;
            font-size: 12px;
            color: #9ca3af;
        }}
    </style>
</head>
<body>
    <div class="email-container">
        <!-- Letterhead -->
        <div class="letterhead">
            <img src="{logo_url}" alt="SolaceSquad" class="logo" style="height: 50px; outline: none; border: none; text-decoration: none;">
        </div>
        
        <!-- Invoice Body -->
        <div class="invoice-body">
            <div class="invoice-title">Tax Invoice / Receipt</div>
            <p style="margin: 0; font-size: 15px; color: #4b5563;">Hi <strong>{user_name}</strong>,</p>
            <p style="margin: 6px 0 0; font-size: 14px; color: #6b7280;">Thank you for your payment. Here are the invoice details for your transaction.</p>
            
            <div class="meta-grid">
                <div class="meta-col">
                    <strong style="color: #374151; display: block; margin-bottom: 4px;">Billed To</strong>
                    {user_name}<br>
                    {to_email}
                </div>
                <div class="meta-col" style="text-align: right;">
                    <strong style="color: #374151; display: block; margin-bottom: 4px;">Invoice Information</strong>
                    Invoice #: <strong>{invoice_number}</strong><br>
                    Date: {date_str}<br>
                    {f'Razorpay Ref: <strong>{payment_id}</strong>' if payment_id else ''}
                </div>
            </div>
            
            <table class="invoice-table">
                <thead>
                    <tr>
                        <th style="text-align: left;">Item Description</th>
                        <th style="text-align: right; width: 120px;">Amount</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td style="color: #111827; font-weight: 600;">{description}</td>
                        <td style="text-align: right; color: #111827; font-weight: 700;">₹{item_cost:,.2f}</td>
                    </tr>
                    <tr>
                        <td colspan="2" style="padding: 10px 0 4px; color: #374151; font-weight: 700; font-size: 13px; border-bottom: none;">Discounts:</td>
                    </tr>
                    {plan_discount_row}
                    {blue_discount_row}
                    {prorate_discount_row}
                </tbody>
            </table>
            
            <div class="totals-section">
                <table style="width: 100%; border-collapse: collapse;">
                    <tr class="totals-row">
                        <td style="padding: 4px 0; color: #4b5563; font-size: 14px;">Actual Cost After Discount</td>
                        <td style="padding: 4px 0; text-align: right; color: #111827; font-size: 14px; font-weight: 600;">₹{cost_after_discount:,.2f}</td>
                    </tr>
                    <tr class="totals-row">
                        <td style="padding: 4px 0; color: #4b5563; font-size: 14px;">Add GST (18%)</td>
                        <td style="padding: 4px 0; text-align: right; color: #111827; font-size: 14px; font-weight: 600;">₹{gst_amount:,.2f}</td>
                    </tr>
                    <tr class="totals-row total">
                        <td style="padding: 15px 0 0; color: #111827; font-size: 18px; font-weight: 800; border-top: 1px solid #e5e7eb;">Total Amount Paid</td>
                        <td style="padding: 15px 0 0; text-align: right; color: #0d9488; font-size: 18px; font-weight: 800; border-top: 1px solid #e5e7eb;">₹{amount:,.2f}</td>
                    </tr>
                </table>
            </div>
        </div>
        
        <!-- Footer -->
        <div class="footer">
            <p style="margin: 0 0 6px;">Questions? Contact us at <a href="mailto:admin@solacesquad.com" style="color: #0d9488; text-decoration: none; font-weight: 600;">admin@solacesquad.com</a></p>
            <p style="margin: 0 0 6px;">GSTIN: 29AFXFS1215D1ZS | <a href="https://www.solacesquad.com" style="color: #0d9488; text-decoration: none; font-weight: 600;">www.solacesquad.com</a></p>
            <p style="margin: 0;">&copy; 2026 SolaceSquad Technologies. All rights reserved.</p>
        </div>
    </div>
</body>
</html>
"""

        text_content = f"""Hi {user_name},
        
Thank you for your payment! Here is your official invoice details for transaction #{invoice_number}.

Item: {description}
Product Cost: ₹{item_cost:,.2f}

Discounts:
1. Plan Discount: {"-₹" + f"{plan_discount:,.2f}" if plan_discount > 0 else "₹0.00"}
2. Blue Plan Discount: {"-₹" + f"{blue_discount:,.2f}" if blue_discount > 0 else "₹0.00"}
3. Prorated Switch Discount: {"-₹" + f"{prorate_discount:,.2f}" if prorate_discount > 0 else "₹0.00"}

Actual Cost After Discount: ₹{cost_after_discount:,.2f}
GST (18%): ₹{gst_amount:,.2f}
Total Paid: ₹{amount:,.2f}

{"Razorpay Ref: " + payment_id if payment_id else ""}

GSTIN: 29AFXFS1215D1ZS
Questions? Contact us at admin@solacesquad.com
— The SolaceSquad Team
"""
        
        # Call the existing SendGrid HTTP API sender
        return _send_raw_appt(to_email, subject, html_content, text_content)

    except Exception as e:
        print(f"[EMAIL] send_payment_invoice_email error: {e}")
        return False


def send_appointment_reminder_email(
    *,
    recipient_type: str,           # "user" | "consultant" | "admin"
    to_email: str,
    user_name: str,
    consultant_name: str,
    appointment_date_utc,          # datetime (UTC)
    duration_minutes: int,
    appointment_id: int,
    user_timezone: str = "Asia/Kolkata"
) -> bool:
    """Send a timezone-aware styled email reminder on the day of appointment."""
    import timezone_utils
    from datetime import datetime
    try:
        user_tz = user_timezone or "Asia/Kolkata"
        tz_display = "IST" if user_tz == "Asia/Kolkata" else user_tz
        local_start = timezone_utils.format_dt_local(appointment_date_utc, user_tz, "%A, %B %d %Y at %I:%M %p") + f" {tz_display}"
        
        dur_label = (f"{duration_minutes} min" if duration_minutes < 60
                     else f"{duration_minutes // 60}h"
                     + (f" {duration_minutes % 60}min" if duration_minutes % 60 else ""))

        is_mirror = os.getenv("ENVIRONMENT") == "mirror"

        # Determine if the appointment date is today in the user's timezone
        appt_local = timezone_utils.to_local(appointment_date_utc, user_tz)
        now_local = timezone_utils.to_local(datetime.utcnow(), user_tz)
        is_today = (appt_local.date() == now_local.date())
        time_phrase = "today" if is_today else f"on {appt_local.strftime('%A, %b %d')}"
        intro_time_phrase = "today" if is_today else f"on <strong>{appt_local.strftime('%A, %b %d')}</strong>"

        if recipient_type == "user":
            subject = f"[SolaceSquad] Reminder: Your consultation {time_phrase} with {consultant_name}"
            if is_mirror:
                subject = f"[REVIEW - USER COPY] {subject}"
            greeting = f"Hi {user_name},"
            intro_text = f"This is a reminder that you have a video consultation scheduled {intro_time_phrase} with your consultant, <strong>{consultant_name}</strong>."
        elif recipient_type == "consultant":
            subject = f"[SolaceSquad] Reminder: Your consultation {time_phrase} with {user_name}"
            if is_mirror:
                subject = f"[REVIEW - CONSULTANT COPY] {subject}"
            greeting = f"Hi {consultant_name},"
            intro_text = f"This is a reminder that you have a video consultation scheduled {intro_time_phrase} with your client, <strong>{user_name}</strong>."
        else:
            subject = f"[SolaceSquad Admin] Upcoming consultation {time_phrase}: {user_name} & {consultant_name}"
            if is_mirror:
                subject = f"[REVIEW - ADMIN COPY] {subject}"
            greeting = "SolaceSquad Administrator Notification,"
            intro_text = f"This is a notification that a consultation session is scheduled {intro_time_phrase} between client <strong>{user_name}</strong> and consultant <strong>{consultant_name}</strong>."

        app_base_url = "https://www.solacesquad.com"
        login_url = f"{app_base_url}/login"

        html_content = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Appointment Reminder</title>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@400;600;800&family=Inter:wght@400;500;700&display=swap" rel="stylesheet">
    <style>
        body {{ font-family: 'Inter', system-ui, sans-serif; background-color: #f4f6f8; margin: 0; padding: 0; -webkit-font-smoothing: antialiased; }}
        .wrapper {{ max-width: 600px; margin: 40px auto; background-color: #ffffff; border-radius: 16px; overflow: hidden; box-shadow: 0 4px 20px rgba(0, 0, 0, 0.05); }}
        .header {{ background-color: #0f766e; padding: 40px 30px; text-align: center; color: #ffffff; }}
        .header h1 {{ font-family: 'Outfit', sans-serif; font-size: 26px; margin: 0 0 8px; font-weight: 800; letter-spacing: -0.5px; }}
        .header p {{ font-size: 16px; margin: 0; opacity: 0.9; font-weight: 500; }}
        .content {{ padding: 40px 30px; color: #374151; line-height: 1.6; }}
        .content p {{ margin: 0 0 20px; font-size: 16px; }}
        .details-card {{ background: #f0fdf4; border: 1px solid #0d9488; border-radius: 12px; padding: 20px; margin: 25px 0; }}
        .details-row {{ display: block; padding: 10px 0; border-bottom: 1px solid rgba(13, 148, 136, 0.1); }}
        .details-row:last-child {{ border-bottom: none; }}
        .details-label {{ font-weight: 700; color: #0f766e; font-size: 14px; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 4px; }}
        .details-value {{ color: #1f2937; font-size: 16px; font-weight: 500; }}
        .btn-container {{ text-align: center; margin: 30px 0 10px; }}
        .btn {{ background-color: #0d9488; color: #ffffff !important; padding: 14px 30px; border-radius: 8px; text-decoration: none; font-family: 'Outfit', sans-serif; font-weight: 600; display: inline-block; box-shadow: 0 4px 10px rgba(13, 148, 136, 0.2); }}
        .footer {{ background-color: #f9fafb; padding: 24px 30px; text-align: center; font-size: 13px; color: #6b7280; border-top: 1px solid #e5e7eb; }}
    </style>
</head>
<body>
    <div class="wrapper">
        <div class="header">
            <h1>SolaceSquad Reminders</h1>
            <p>Your Consultation Day-of Alert</p>
        </div>
        <div class="content">
            <p>{greeting}</p>
            <p>{intro_text}</p>
            
            <div class="details-card">
                <div class="details-row">
                    <div class="details-label">Client</div>
                    <div class="details-value">{user_name}</div>
                </div>
                <div class="details-row">
                    <div class="details-label">Consultant</div>
                    <div class="details-value">{consultant_name}</div>
                </div>
                <div class="details-row">
                    <div class="details-label">Appointment Time</div>
                    <div class="details-value">{local_start}</div>
                </div>
                <div class="details-row">
                    <div class="details-label">Duration</div>
                    <div class="details-value">{dur_label}</div>
                </div>
            </div>

            <p>Please click the button below to log in to your dashboard and join the consultation:</p>
            
            <div class="btn-container">
                <a href="{login_url}" class="btn">Login to the app to join the call</a>
            </div>
        </div>
        <div class="footer">
            <p style="margin: 0 0 6px;">Questions? Contact us at <a href="mailto:admin@solacesquad.com" style="color: #0d9488; text-decoration: none; font-weight: 600;">admin@solacesquad.com</a></p>
            <p style="margin: 0;">&copy; 2026 SolaceSquad Technologies. All rights reserved.</p>
        </div>
    </div>
</body>
</html>
"""

        text_content = f"""Hi {user_name if recipient_type == 'user' else (consultant_name if recipient_type == 'consultant' else 'Admin')},

This is a reminder that a video consultation session is scheduled today between client {user_name} and consultant {consultant_name}.

Appointment Details:
- Client: {user_name}
- Consultant: {consultant_name}
- Time: {local_start}
- Duration: {dur_label}

To join the call, log in to your dashboard at:
{login_url}

— The SolaceSquad Team
"""
        return _send_raw_appt(to_email, subject, html_content, text_content)

    except Exception as e:
        print(f"[EMAIL] send_appointment_reminder_email error: {e}")
        return False


def send_quick_consult_consultant_email(
    *,
    to_email: str,
    to_name: str,
    qc_id: str,
    appointment_time_str: str,
    duration_minutes: int,
    payout_amount: float = 0.0,
    app_base_url: str = "https://www.solacesquad.com",
    consultation_mode: str = "telephony",
    room_url: str = "",
    client_name: str = "",
    client_phone: str = "",
    consultant_name: str = "",
    consultant_specialization: str = "",
    is_admin: bool = False,
) -> bool:
    """
    Send an instant booking notification email for a new Quick Consultation.
    Supports both Consultant recipient and Admin recipient.
    """
    try:
        # Check if recipient is Admin or explicitly requested as Admin
        clean_name = (to_name or "").strip()
        lower_name = clean_name.lower()
        if is_admin or lower_name == "admin" or lower_name.startswith("admin (") or lower_name.startswith("admin for"):
            is_admin = True
            clean_name = "Admin"

        dashboard_url = f"{app_base_url.rstrip('/')}/admin" if is_admin else f"{app_base_url.rstrip('/')}/consultant"
        is_webrtc = (consultation_mode == "webrtc")
        target_room_url = room_url or f"{app_base_url.rstrip('/')}/quick-consult/room?id={qc_id}"
        
        if is_admin:
            mode_title = "⚡ [Admin Alert] New WebRTC Quick Consultation Booked" if is_webrtc else "📞 [Admin Alert] New Phone Quick Consultation Booked"
        else:
            mode_title = "⚡ [SolaceSquad] New WebRTC Quick Consultation Booked" if is_webrtc else "📞 [SolaceSquad] New Phone Quick Consultation Booked"
        subject = f"{mode_title} — ID: {qc_id}"

        mode_badge = "🌐 In-Browser Web Call" if is_webrtc else "📞 Telephony Phone Call"

        # Client details formatting
        client_label = "Booked By" if is_admin else "Client"
        if client_name and client_phone:
            client_display = f"{client_name} ({client_phone})"
        elif client_phone:
            client_display = client_phone
        elif client_name:
            client_display = client_name
        else:
            client_display = "Guest Client"

        # Consultant details formatting
        c_display = consultant_name or (clean_name if not is_admin else "")
        if consultant_name and consultant_specialization:
            c_display = f"{consultant_name} ({consultant_specialization})"

        subheading = (
            f"A client has scheduled an on-demand consultation ({mode_badge})"
            if is_admin
            else f"A client has scheduled an on-demand consultation with you ({mode_badge})"
        )

        consultant_row_html = f"""
                <div class="details-row">
                    <span class="details-label">Consultant</span>
                    <span class="details-value">{c_display}</span>
                </div>
        """ if (is_admin and c_display) else ""

        client_row_html = f"""
                <div class="details-row">
                    <span class="details-label">{client_label}</span>
                    <span class="details-value">{client_display}</span>
                </div>
        """ if client_display else ""

        if is_webrtc:
            instructions_html = f"""
                <div class="alert-box" style="background-color: #f5f3ff; border-left: 4px solid #7c3aed; color: #4c1d95;">
                    🌐 <strong>WebRTC Call Room:</strong> This session will take place via in-browser video/audio call. You can join directly or click below:
                    <br><br>
                    <a href="{target_room_url}" style="color: #6d28d9; font-weight: 700; text-decoration: underline;">Open WebRTC Call Room &rarr;</a>
                    <br><span style="font-size: 12px; color: #6b7280;">(Call room unlocks 5 minutes before scheduled start time)</span>
                </div>
            """
        else:
            if is_admin:
                instructions_html = f"""
                    <div class="alert-box">
                        📞 <strong>Telephony Call:</strong> The automated system will bridge a call between the consultant and client at the scheduled time.
                    </div>
                """
            else:
                instructions_html = f"""
                    <div class="alert-box">
                        📞 <strong>Incoming Call:</strong> We will call you on your registered mobile number to connect you with the client at the scheduled time. Please keep your phone reachable.
                    </div>
                """

        primary_btn_url = target_room_url if is_webrtc else dashboard_url
        primary_btn_text = "🌐 Join Web Call Room" if is_webrtc else ("Open Admin Dashboard" if is_admin else "Open Consultant Dashboard")

        html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>New Quick Consultation</title>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@400;600;800&family=Inter:wght@400;500;700&display=swap" rel="stylesheet">
    <style>
        body {{ font-family: 'Inter', system-ui, sans-serif; background-color: #f4f6f8; margin: 0; padding: 0; -webkit-font-smoothing: antialiased; }}
        .wrapper {{ max-width: 600px; margin: 40px auto; background-color: #ffffff; border-radius: 16px; overflow: hidden; box-shadow: 0 4px 20px rgba(0, 0, 0, 0.05); }}
        .header {{ background: linear-gradient(135deg, #0f766e 0%, #0d9488 100%); padding: 36px 30px; text-align: center; color: #ffffff; }}
        .header h1 {{ font-family: 'Outfit', sans-serif; font-size: 24px; margin: 0 0 8px; font-weight: 800; letter-spacing: -0.5px; }}
        .header p {{ font-size: 15px; margin: 0; opacity: 0.95; font-weight: 500; }}
        .content {{ padding: 36px 30px; color: #374151; line-height: 1.6; }}
        .details-card {{ background: #f0fdf4; border: 1px solid #0d9488; border-radius: 12px; padding: 20px; margin: 24px 0; }}
        .details-row {{ display: flex; justify-content: space-between; align-items: center; gap: 12px; padding: 10px 0; border-bottom: 1px solid rgba(13, 148, 136, 0.15); }}
        .details-row:last-child {{ border-bottom: none; }}
        .details-label {{ font-weight: 700; color: #0f766e; font-size: 14px; text-transform: uppercase; letter-spacing: 0.5px; min-width: 120px; }}
        .details-value {{ color: #111827; font-size: 15px; font-weight: 600; text-align: right; word-break: break-word; }}
        .alert-box {{ background-color: #fefce8; border-left: 4px solid #eab308; padding: 14px 18px; border-radius: 6px; margin: 20px 0; font-size: 14px; color: #713f12; }}
        .btn-container {{ text-align: center; margin: 28px 0 10px; }}
        .btn {{ background-color: #0d9488; color: #ffffff !important; padding: 14px 28px; border-radius: 8px; text-decoration: none; font-family: 'Outfit', sans-serif; font-weight: 700; display: inline-block; box-shadow: 0 4px 12px rgba(13, 148, 136, 0.25); }}
        .footer {{ background-color: #f9fafb; padding: 20px 30px; text-align: center; font-size: 13px; color: #6b7280; border-top: 1px solid #e5e7eb; }}
    </style>
</head>
<body>
    <div class="wrapper">
        <div class="header">
            <h1>⚡ New Quick Consultation Booked</h1>
            <p>{subheading}</p>
        </div>
        <div class="content">
            <p>Hi <strong>{clean_name}</strong>,</p>
            <p>A new Quick Consultation has been confirmed and paid. Here are the session details:</p>
            
            <div class="details-card">
                <div class="details-row">
                    <span class="details-label">Session ID</span>
                    <span class="details-value">{qc_id}</span>
                </div>
                {consultant_row_html}
                {client_row_html}
                <div class="details-row">
                    <span class="details-label">Mode</span>
                    <span class="details-value">{mode_badge}</span>
                </div>
                <div class="details-row">
                    <span class="details-label">Appointment Time</span>
                    <span class="details-value">{appointment_time_str}</span>
                </div>
                <div class="details-row" style="border-bottom: none;">
                    <span class="details-label">Duration</span>
                    <span class="details-value">{duration_minutes} Minutes</span>
                </div>
            </div>

            {instructions_html}

            <div class="btn-container">
                <a href="{primary_btn_url}" class="btn">{primary_btn_text}</a>
            </div>
        </div>
        <div class="footer">
            <p style="margin: 0 0 6px;">Questions? Contact us at <a href="mailto:admin@solacesquad.com" style="color: #0d9488; text-decoration: none; font-weight: 600;">admin@solacesquad.com</a></p>
            <p style="margin: 0;">&copy; 2026 SolaceSquad Technologies. All rights reserved.</p>
        </div>
    </div>
</body>
</html>
"""

        consultant_line = f"- Consultant: {c_display}\n" if (is_admin and c_display) else ""
        client_line = f"- {client_label}: {client_display}\n" if client_display else ""

        text_content = f"""Hi {clean_name},

A new Quick Consultation ({mode_badge}) has been confirmed and paid on SolaceSquad!

Session Details:
- Session ID: {qc_id}
{consultant_line}{client_line}- Mode: {mode_badge}
- Time: {appointment_time_str}
- Duration: {duration_minutes} Minutes

{"WebRTC Call Room: " + target_room_url if is_webrtc else ("Telephony call bridge scheduled." if is_admin else "We will call you on your registered mobile number to connect you with the client at the scheduled time.")}

{primary_btn_text}:
{primary_btn_url}

— The SolaceSquad Team
"""
        return _send_raw_appt(to_email, subject, html_content, text_content)

    except Exception as e:
        print(f"[EMAIL] send_quick_consult_consultant_email error: {e}")
        return False


def send_quick_consult_admin_email(
    *,
    to_email: str,
    qc_id: str,
    appointment_time_str: str,
    duration_minutes: int,
    consultant_name: str,
    consultant_specialization: str = "",
    client_name: str = "",
    client_phone: str = "",
    app_base_url: str = "https://www.solacesquad.com",
    consultation_mode: str = "telephony",
    room_url: str = "",
) -> bool:
    """
    Dedicated helper to send instant booking notification email to Admin for Quick Consultation.
    Explicitly addresses Admin, and includes Consultant and Client details.
    """
    return send_quick_consult_consultant_email(
        to_email=to_email,
        to_name="Admin",
        qc_id=qc_id,
        appointment_time_str=appointment_time_str,
        duration_minutes=duration_minutes,
        app_base_url=app_base_url,
        consultation_mode=consultation_mode,
        room_url=room_url,
        client_name=client_name,
        client_phone=client_phone,
        consultant_name=consultant_name,
        consultant_specialization=consultant_specialization,
        is_admin=True,
    )


def send_quick_consult_missed_call_alert(
    *,
    to_email: str,
    to_name: str,
    qc_id: str,
    client_phone_masked: str,
    app_base_url: str = "https://www.solacesquad.com",
) -> bool:
    """
    Alert the consultant when their phone did not answer an automated Quick Consultation call bridge.
    """
    try:
        dashboard_url = f"{app_base_url.rstrip('/')}/consultant"
        subject = f"⚠️ [Action Required] Missed Quick Consultation Call — ID: {qc_id}"

        html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Missed Quick Consultation Call</title>
    <style>
        body {{ font-family: system-ui, sans-serif; background-color: #f4f6f8; margin: 0; padding: 0; }}
        .wrapper {{ max-width: 600px; margin: 40px auto; background-color: #ffffff; border-radius: 16px; overflow: hidden; box-shadow: 0 4px 20px rgba(0,0,0,0.05); }}
        .header {{ background: linear-gradient(135deg, #b91c1c 0%, #dc2626 100%); padding: 32px 24px; text-align: center; color: #ffffff; }}
        .content {{ padding: 32px 24px; color: #374151; line-height: 1.6; }}
        .alert-card {{ background: #fef2f2; border: 1px solid #f87171; border-radius: 12px; padding: 18px; margin: 20px 0; }}
        .btn {{ background-color: #0d9488; color: #ffffff !important; padding: 14px 28px; border-radius: 8px; text-decoration: none; font-weight: 700; display: inline-block; }}
    </style>
</head>
<body>
    <div class="wrapper">
        <div class="header">
            <h1 style="margin:0;font-size:22px;">⚠️ Missed Quick Consultation Call</h1>
            <p style="margin:6px 0 0;font-size:14px;opacity:0.9;">Session ID: {qc_id}</p>
        </div>
        <div class="content">
            <p>Hi <strong>{to_name}</strong>,</p>
            <div class="alert-card">
                <strong>Our automated system attempted to dial your registered phone for Quick Consultation ({qc_id}), but the call was not answered or was busy.</strong>
            </div>
            <p>The client is waiting for the session. Please log in to your dashboard and click <strong>"📞 Call Client"</strong> to connect immediately:</p>
            <div style="text-align: center; margin: 28px 0;">
                <a href="{dashboard_url}" class="btn">Open Dashboard & Call Client</a>
            </div>
            <p style="font-size: 13px; color: #6b7280;">If you are facing network or carrier issues, please ensure your phone is reachable and not on Do Not Disturb mode.</p>
        </div>
    </div>
</body>
</html>
"""
        text_content = f"""Hi {to_name},

Our automated system attempted to dial your registered mobile number for Quick Consultation ({qc_id}), but the call was not answered.

The client is waiting. Please open your dashboard and click 'Call Client' to connect immediately:
{dashboard_url}

— SolaceSquad Support
"""
        return _send_raw_appt(to_email, subject, html_content, text_content)
    except Exception as e:
        print(f"[EMAIL] send_quick_consult_missed_call_alert error: {e}")
        return False


def send_quick_consult_client_unreachable_alert(
    *,
    to_email: str,
    to_name: str,
    qc_id: str,
    client_phone_masked: str,
    app_base_url: str = "https://www.solacesquad.com",
) -> bool:
    """
    Alert the consultant when the client's phone was unreachable or not answered.
    """
    try:
        dashboard_url = f"{app_base_url.rstrip('/')}/consultant"
        subject = f"ℹ️ SolaceSquad: Client Unreachable for Quick Consultation — ID: {qc_id}"

        html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Client Unreachable</title>
    <style>
        body {{ font-family: system-ui, sans-serif; background-color: #f4f6f8; margin: 0; padding: 0; }}
        .wrapper {{ max-width: 600px; margin: 40px auto; background-color: #ffffff; border-radius: 16px; overflow: hidden; }}
        .header {{ background: linear-gradient(135deg, #0f766e 0%, #0d9488 100%); padding: 32px 24px; text-align: center; color: #ffffff; }}
        .content {{ padding: 32px 24px; color: #374151; line-height: 1.6; }}
        .info-card {{ background: #fefce8; border: 1px solid #facc15; border-radius: 12px; padding: 18px; margin: 20px 0; color: #713f12; }}
        .btn {{ background-color: #0d9488; color: #ffffff !important; padding: 14px 28px; border-radius: 8px; text-decoration: none; font-weight: 700; display: inline-block; }}
    </style>
</head>
<body>
    <div class="wrapper">
        <div class="header">
            <h1 style="margin:0;font-size:22px;">ℹ️ Client Unreachable</h1>
            <p style="margin:6px 0 0;font-size:14px;opacity:0.9;">Session ID: {qc_id}</p>
        </div>
        <div class="content">
            <p>Hi <strong>{to_name}</strong>,</p>
            <div class="info-card">
                We successfully connected to your phone for Quick Consultation ({qc_id}), but the client's phone ({client_phone_masked}) did not answer or was busy.
            </div>
            <p>You can wait a moment and click <strong>"📞 Call Client"</strong> from your dashboard to re-dial when ready:</p>
            <div style="text-align: center; margin: 28px 0;">
                <a href="{dashboard_url}" class="btn">Open Dashboard & Retry</a>
            </div>
        </div>
    </div>
</body>
</html>
"""
        text_content = f"""Hi {to_name},

We connected to your phone for Quick Consultation ({qc_id}), but the client ({client_phone_masked}) did not answer.
You can retry calling from your dashboard:
{dashboard_url}

— SolaceSquad Support
"""
        return _send_raw_appt(to_email, subject, html_content, text_content)
    except Exception as e:
        print(f"[EMAIL] send_quick_consult_client_unreachable_alert error: {e}")
        return False


def send_quick_consult_admin_unreachable_alert(
    *,
    to_email: str,
    consultant_name: str,
    consultant_phone: str,
    qc_id: str,
    client_phone: str,
    appointment_time_str: str,
    voucher_code: Optional[str] = None,
    app_base_url: str = "https://www.solacesquad.com",
) -> bool:
    """
    Alert Admin when a consultant failed to answer both initial call and 2-minute auto-retry call.
    Includes 100% discount voucher generated for client reschedule.
    """
    try:
        admin_url = f"{app_base_url.rstrip('/')}/admin"
        subject = f"🚨 [Admin Alert] Consultant Unreachable for QC {qc_id} — {consultant_name}"

        voucher_row_html = f"""
                <tr>
                    <td>100% Reschedule Voucher:</td>
                    <td><strong style="color: #0d9488; font-size: 15px;"><code>{voucher_code}</code></strong> (Single-use)</td>
                </tr>""" if voucher_code else ""

        html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Consultant Unreachable Alert</title>
    <style>
        body {{ font-family: system-ui, sans-serif; background-color: #f4f6f8; margin: 0; padding: 0; }}
        .wrapper {{ max-width: 600px; margin: 40px auto; background-color: #ffffff; border-radius: 16px; overflow: hidden; box-shadow: 0 4px 20px rgba(0,0,0,0.05); }}
        .header {{ background: linear-gradient(135deg, #991b1b 0%, #b91c1c 100%); padding: 32px 24px; text-align: center; color: #ffffff; }}
        .content {{ padding: 32px 24px; color: #374151; line-height: 1.6; }}
        .alert-card {{ background: #fef2f2; border: 1px solid #ef4444; border-radius: 12px; padding: 18px; margin: 20px 0; }}
        .info-table {{ width: 100%; border-collapse: collapse; margin: 16px 0; font-size: 14px; }}
        .info-table td {{ padding: 8px 12px; border-bottom: 1px solid #e5e7eb; }}
        .info-table td:first-child {{ font-weight: bold; color: #4b5563; width: 40%; }}
        .btn {{ background-color: #0d9488; color: #ffffff !important; padding: 12px 24px; border-radius: 8px; text-decoration: none; font-weight: 700; display: inline-block; }}
    </style>
</head>
<body>
    <div class="wrapper">
        <div class="header">
            <h1 style="margin:0;font-size:22px;">🚨 Consultant Unreachable Alert</h1>
            <p style="margin:6px 0 0;font-size:14px;opacity:0.9;">Quick Consultation ID: {qc_id}</p>
        </div>
        <div class="content">
            <div class="alert-card">
                <strong style="color: #991b1b; font-size: 15px;">Both automated call attempts to the consultant were missed or not answered.</strong>
                <p style="margin: 6px 0 0; font-size: 13px; color: #7f1d1d;">The system attempted the initial call and a 2-minute auto-retry. A 100% discount reschedule voucher has been generated and sent to the client via SMS.</p>
            </div>

            <table class="info-table">
                <tr>
                    <td>Quick Consult ID:</td>
                    <td><code>{qc_id}</code></td>
                </tr>
                <tr>
                    <td>Scheduled Time:</td>
                    <td>{appointment_time_str}</td>
                </tr>
                <tr>
                    <td>Consultant:</td>
                    <td><strong>{consultant_name}</strong> ({consultant_phone})</td>
                </tr>
                <tr>
                    <td>Client Mobile:</td>
                    <td><strong>{client_phone}</strong></td>
                </tr>
                <tr>
                    <td>Call Status:</td>
                    <td><span style="background: #fee2e2; color: #991b1b; padding: 2px 8px; border-radius: 4px; font-weight: bold;">consultant_unreachable</span></td>
                </tr>{voucher_row_html}
            </table>

            <div style="text-align: center; margin: 28px 0;">
                <a href="{admin_url}" class="btn">Open Admin Console</a>
            </div>
            <p style="font-size: 12px; color: #9ca3af; text-align: center;">SolaceSquad Automated Telephony Monitoring System</p>
        </div>
    </div>
</body>
</html>
"""
        voucher_text = f"100% Reschedule Voucher: {voucher_code}\n" if voucher_code else ""
        text_content = f"""[Admin Alert] Consultant Unreachable for QC {qc_id}

Consultant {consultant_name} ({consultant_phone}) did not answer both automated call attempts for Quick Consultation {qc_id} scheduled at {appointment_time_str}.

Client Phone: {client_phone}
Call Status: consultant_unreachable
{voucher_text}
An alert and 100% discount voucher have been dispatched to the client for rescheduling.
Admin Console: {admin_url}

— SolaceSquad Telephony Engine
"""
        return _send_raw_appt(to_email, subject, html_content, text_content)
    except Exception as e:
        print(f"[EMAIL] send_quick_consult_admin_unreachable_alert error: {e}")
        return False


def send_quick_consult_client_cancelled_alert(
    *,
    to_email: str,
    recipient_role: str,  # "consultant" or "admin"
    recipient_name: str,
    consultant_name: str,
    qc_id: str,
    client_phone_masked: str,
    appointment_time_str: str,
    app_base_url: str = "https://www.solacesquad.com",
) -> bool:
    """
    Alert Consultant / Admin when a Quick Consultation is cancelled after 3 missed call attempts to the client.
    """
    try:
        dashboard_url = f"{app_base_url.rstrip('/')}/consultant" if recipient_role == "consultant" else f"{app_base_url.rstrip('/')}/admin"
        subject = f"🚫 [Call Cancelled] Client Unreachable (3 Attempts) — QC {qc_id}"

        html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Call Cancelled - Client Unreachable</title>
    <style>
        body {{ font-family: system-ui, sans-serif; background-color: #f4f6f8; margin: 0; padding: 0; }}
        .wrapper {{ max-width: 600px; margin: 40px auto; background-color: #ffffff; border-radius: 16px; overflow: hidden; box-shadow: 0 4px 20px rgba(0,0,0,0.05); }}
        .header {{ background: linear-gradient(135deg, #475569 0%, #334155 100%); padding: 32px 24px; text-align: center; color: #ffffff; }}
        .content {{ padding: 32px 24px; color: #374151; line-height: 1.6; }}
        .info-card {{ background: #f8fafc; border: 1px solid #cbd5e1; border-radius: 12px; padding: 18px; margin: 20px 0; }}
        .info-table {{ width: 100%; border-collapse: collapse; margin: 16px 0; font-size: 14px; }}
        .info-table td {{ padding: 8px 12px; border-bottom: 1px solid #e2e8f0; }}
        .info-table td:first-child {{ font-weight: bold; color: #475569; width: 40%; }}
        .btn {{ background-color: #0d9488; color: #ffffff !important; padding: 12px 24px; border-radius: 8px; text-decoration: none; font-weight: 700; display: inline-block; }}
    </style>
</head>
<body>
    <div class="wrapper">
        <div class="header">
            <h1 style="margin:0;font-size:22px;">🚫 Consultation Call Cancelled</h1>
            <p style="margin:6px 0 0;font-size:14px;opacity:0.9;">Quick Consultation ID: {qc_id}</p>
        </div>
        <div class="content">
            <p>Hi <strong>{recipient_name}</strong>,</p>
            <div class="info-card">
                <strong>Our automated system attempted to reach the client 3 times for Quick Consultation ({qc_id}), but the client did not answer any of the calls.</strong>
                <p style="margin: 6px 0 0; font-size: 13px; color: #64748b;">The call has now been cancelled and an automated cancellation notification has been sent to the client's mobile number.</p>
            </div>

            <table class="info-table">
                <tr>
                    <td>Quick Consult ID:</td>
                    <td><code>{qc_id}</code></td>
                </tr>
                <tr>
                    <td>Scheduled Time:</td>
                    <td>{appointment_time_str}</td>
                </tr>
                <tr>
                    <td>Consultant:</td>
                    <td><strong>{consultant_name}</strong></td>
                </tr>
                <tr>
                    <td>Client Contact:</td>
                    <td><strong>{client_phone_masked}</strong></td>
                </tr>
                <tr>
                    <td>Status:</td>
                    <td><span style="background: #e2e8f0; color: #334155; padding: 2px 8px; border-radius: 4px; font-weight: bold;">cancelled_client_no_answer</span></td>
                </tr>
            </table>

            <div style="text-align: center; margin: 28px 0;">
                <a href="{dashboard_url}" class="btn">Open Dashboard</a>
            </div>
            <p style="font-size: 12px; color: #94a3b8; text-align: center;">SolaceSquad Automated Telephony System</p>
        </div>
    </div>
</body>
</html>
"""
        text_content = f"""Hi {recipient_name},

Our automated system attempted to reach the client 3 times for Quick Consultation {qc_id} ({appointment_time_str}), but the client did not answer.

The call has been cancelled. An automated notification was dispatched to the client.
Dashboard: {dashboard_url}

— SolaceSquad Telephony System
"""
        return _send_raw_appt(to_email, subject, html_content, text_content)
    except Exception as e:
        print(f"[EMAIL] send_quick_consult_client_cancelled_alert error: {e}")
        return False


