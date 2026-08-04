"""
Patch script run during Docker build to fix Jinja2 syntax errors in call_room.html.
"""
import re

path = 'templates/pages/call_room.html'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

original = content

# Fix 1: spaced braces { { appointment.user_id } }
content = content.replace('{ { appointment.user_id } }', '{{ appointment.user_id }}')

# Fix 2: single closing brace {{ appointment.user_id } on its own line followed by };
content = re.sub(
    r'const patientId = \{\{ appointment\.user_id \}[\s\S]{0,10}?\};',
    'const patientId = {{ appointment.user_id }};',
    content
)

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)

# Verify
with open(path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

line_680 = lines[679].strip() if len(lines) > 679 else '(file too short)'
print(f"Line 680 after patch: {line_680}")

if '{{ appointment.user_id }};' in line_680:
    print("SUCCESS: Template is correctly patched")
elif '{ appointment.user_id }' in line_680:
    print("WARNING: Line 680 still has bug!")
    raise SystemExit(1)
else:
    print("INFO: Line 680 did not match either pattern (may already be fixed)")
