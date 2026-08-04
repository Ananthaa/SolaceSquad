#!/usr/bin/env python3
"""
Remove all Unicode emoji characters from firebase_otp.py
"""

# Read the file
with open('backend/firebase_otp.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Replace all Unicode emojis with ASCII equivalents
replacements = {
    '✅': '[OK]',
    '❌': '[X]',
    '📤': '[SEND]',
    '📧': '[EMAIL]',
    '🔐': '[LOCK]',
}

for emoji, replacement in replacements.items():
    content = content.replace(emoji, replacement)

# Write back
with open('backend/firebase_otp.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Fixed all Unicode characters in firebase_otp.py")
