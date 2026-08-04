import re

# Read the file
with open('backend/templates/pages/call_room.html', 'r', encoding='latin-1') as f:
    content = f.read()

# Fix the incomplete Jinja2 variable
content = content.replace(
    'const patientId = {{ appointment.user_id }}',
    'const patientId = {{ appointment.user_id }};'
)

# Write back
with open('backend/templates/pages/call_room.html', 'w', encoding='utf-8') as f:
    f.write(content)

print("Fixed patientId declaration!")
