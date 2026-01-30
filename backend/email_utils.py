import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional


class EmailConfig:
    """Email configuration from environment variables"""
    SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
    SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USERNAME = os.getenv("SMTP_USERNAME", "")
    SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
    FROM_EMAIL = os.getenv("FROM_EMAIL", os.getenv("SMTP_USERNAME", ""))
    FROM_NAME = os.getenv("FROM_NAME", "SolaceSquad")


def send_password_reset_email(to_email: str, reset_token: str, user_name: str) -> bool:
    """
    Send password reset email to user
    
    Args:
        to_email: Recipient email address
        reset_token: Password reset token
        user_name: User's name for personalization
        
    Returns:
        True if email sent successfully, False otherwise
    """
    try:
        # Check if email is configured
        if not EmailConfig.SMTP_USERNAME or not EmailConfig.SMTP_PASSWORD:
            print("WARNING: Email not configured. Reset link would be:")
            print(f"http://localhost:8000/reset-password/{reset_token}")
            return True  # Return True for development/testing
        
        # Create reset link (adjust domain for production)
        base_url = os.getenv("BASE_URL", "http://localhost:8000")
        reset_link = f"{base_url}/reset-password/{reset_token}"
        
        # Create message
        msg = MIMEMultipart("alternative")
        msg["Subject"] = "Password Reset Request - SolaceSquad"
        msg["From"] = f"{EmailConfig.FROM_NAME} <{EmailConfig.FROM_EMAIL}>"
        msg["To"] = to_email
        
        # Email body (HTML)
        html_body = f"""
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
                    padding: 20px;
                }}
                .header {{
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    color: white;
                    padding: 30px;
                    text-align: center;
                    border-radius: 10px 10px 0 0;
                }}
                .content {{
                    background: #f9fafb;
                    padding: 30px;
                    border-radius: 0 0 10px 10px;
                }}
                .button {{
                    display: inline-block;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    color: white;
                    padding: 14px 28px;
                    text-decoration: none;
                    border-radius: 8px;
                    margin: 20px 0;
                    font-weight: 600;
                }}
                .footer {{
                    text-align: center;
                    margin-top: 30px;
                    color: #6b7280;
                    font-size: 14px;
                }}
                .warning {{
                    background: #fef3c7;
                    border-left: 4px solid #f59e0b;
                    padding: 15px;
                    margin: 20px 0;
                    border-radius: 4px;
                }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>🧘 SolaceSquad</h1>
                <p>Password Reset Request</p>
            </div>
            <div class="content">
                <p>Hi {user_name},</p>
                
                <p>We received a request to reset your password for your SolaceSquad account. Click the button below to create a new password:</p>
                
                <center>
                    <a href="{reset_link}" class="button">Reset Password</a>
                </center>
                
                <p>Or copy and paste this link into your browser:</p>
                <p style="background: white; padding: 10px; border-radius: 4px; word-break: break-all;">
                    {reset_link}
                </p>
                
                <div class="warning">
                    <strong>⚠️ Important:</strong> This link will expire in 24 hours. If you didn't request this password reset, please ignore this email or contact support if you have concerns.
                </div>
                
                <p>Best regards,<br>The SolaceSquad Team</p>
            </div>
            <div class="footer">
                <p>This is an automated email. Please do not reply to this message.</p>
                <p>&copy; 2026 SolaceSquad. All rights reserved.</p>
            </div>
        </body>
        </html>
        """
        
        # Plain text version
        text_body = f"""
        Hi {user_name},
        
        We received a request to reset your password for your SolaceSquad account.
        
        Click the link below to create a new password:
        {reset_link}
        
        This link will expire in 24 hours.
        
        If you didn't request this password reset, please ignore this email.
        
        Best regards,
        The SolaceSquad Team
        """
        
        # Attach both versions
        part1 = MIMEText(text_body, "plain")
        part2 = MIMEText(html_body, "html")
        msg.attach(part1)
        msg.attach(part2)
        
        # Send email
        with smtplib.SMTP(EmailConfig.SMTP_HOST, EmailConfig.SMTP_PORT) as server:
            server.starttls()
            server.login(EmailConfig.SMTP_USERNAME, EmailConfig.SMTP_PASSWORD)
            server.send_message(msg)
        
        print(f"Password reset email sent to {to_email}")
        return True
        
    except Exception as e:
        print(f"Error sending email: {str(e)}")
        # For development, print the reset link
        print(f"Reset link (for development): http://localhost:8000/reset-password/{reset_token}")
        return False


def send_welcome_email(to_email: str, user_name: str) -> bool:
    """
    Send welcome email to new user (optional)
    
    Args:
        to_email: Recipient email address
        user_name: User's name for personalization
        
    Returns:
        True if email sent successfully, False otherwise
    """
    try:
        # Check if email is configured
        if not EmailConfig.SMTP_USERNAME or not EmailConfig.SMTP_PASSWORD:
            print(f"Welcome email would be sent to {to_email}")
            return True
        
        # Create message
        msg = MIMEMultipart("alternative")
        msg["Subject"] = "Welcome to SolaceSquad! 🧘"
        msg["From"] = f"{EmailConfig.FROM_NAME} <{EmailConfig.FROM_EMAIL}>"
        msg["To"] = to_email
        
        # Email body
        html_body = f"""
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
                    padding: 20px;
                }}
                .header {{
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    color: white;
                    padding: 30px;
                    text-align: center;
                    border-radius: 10px 10px 0 0;
                }}
                .content {{
                    background: #f9fafb;
                    padding: 30px;
                    border-radius: 0 0 10px 10px;
                }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>🧘 Welcome to SolaceSquad!</h1>
            </div>
            <div class="content">
                <p>Hi {user_name},</p>
                <p>Thank you for joining SolaceSquad! We're excited to support you on your wellbeing journey.</p>
                <p>Get started by exploring our features and connecting with our professional consultants.</p>
                <p>Best regards,<br>The SolaceSquad Team</p>
            </div>
        </body>
        </html>
        """
        
        text_body = f"Hi {user_name},\n\nWelcome to SolaceSquad! We're excited to support you on your wellbeing journey.\n\nBest regards,\nThe SolaceSquad Team"
        
        part1 = MIMEText(text_body, "plain")
        part2 = MIMEText(html_body, "html")
        msg.attach(part1)
        msg.attach(part2)
        
        with smtplib.SMTP(EmailConfig.SMTP_HOST, EmailConfig.SMTP_PORT) as server:
            server.starttls()
            server.login(EmailConfig.SMTP_USERNAME, EmailConfig.SMTP_PASSWORD)
            server.send_message(msg)
        
        return True
        
    except Exception as e:
        print(f"Error sending welcome email: {str(e)}")
        return False
