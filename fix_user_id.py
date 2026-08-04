import re

# Read the file
with open('backend/templates/pages/call_room.html', 'r', encoding='latin-1') as f:
    content = f.read()

# Fix the malformed Jinja2 variable with spaces
content = content.replace(
    'user_id: { { appointment.user_id } }',
    'user_id: {{ appointment.user_id }}'
)

# Write back
with open('backend/templates/pages/call_room.html', 'w', encoding='utf-8') as f:
    f.write(content)

print("Fixed user_id Jinja2 variable!")
