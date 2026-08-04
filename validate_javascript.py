import re
import json

# Read the file
with open(r'c:\Anantha\Projects\Soul Squad\backend\templates\pages\call_room.html', 'r', encoding='utf-8') as f:
    content = f.read()

# Extract all script tags
script_pattern = r'<script[^>]*>(.*?)</script>'
scripts = re.findall(script_pattern, content, re.DOTALL)

print(f"Found {len(scripts)} script blocks\n")

# Check for common JavaScript errors
errors = []

# Check 1: Find the showConsentModal function
if 'function showConsentModal()' in content:
    print("✓ showConsentModal function found")
    # Get the function
    match = re.search(r'function showConsentModal\(\)\s*{([^}]+)}', content, re.DOTALL)
    if match:
        func_body = match.group(1)
        print(f"  Function body:\n{func_body[:200]}")
else:
    errors.append("✗ showConsentModal function NOT found")

# Check 2: Find the button with onclick
if 'onclick="showConsentModal()"' in content:
    print("\n✓ Button with onclick='showConsentModal()' found")
else:
    errors.append("✗ Button onclick NOT found")

# Check 3: Check for unclosed braces in the area around line 680
lines = content.split('\n')
for i in range(675, min(720, len(lines))):
    line = lines[i]
    if 'const patientId' in line:
        print(f"\n✓ Line {i+1}: {line.strip()}")
        # Check next 10 lines for structure
        for j in range(i, min(i+15, len(lines))):
            print(f"  {j+1}: {lines[j].rstrip()}")
        break

# Check 4: Look for syntax errors - unmatched braces
brace_count = 0
in_script = False
for i, line in enumerate(lines, 1):
    if '<script' in line:
        in_script = True
    if '</script>' in line:
        in_script = False
        
    if in_script:
        # Count braces
        brace_count += line.count('{') - line.count('}')
        
        # Check for common errors
        if '{{ ' in line and '}}' not in line and 'appointment' in line:
            errors.append(f"Line {i}: Possible Jinja2 template error: {line.strip()}")

print(f"\n\nBrace balance in scripts: {brace_count}")
if brace_count != 0:
    errors.append(f"Unbalanced braces: {brace_count}")

# Check 5: Look for the specific error pattern
if 'const patientId = {{ appointment.user_id }' in content and 'const patientId = {{ appointment.user_id }}' not in content:
    errors.append("Template syntax error: Missing closing }} in patientId")

print("\n" + "="*60)
if errors:
    print("ERRORS FOUND:")
    for error in errors:
        print(f"  {error}")
else:
    print("✓ No obvious errors found")

# Check if the script is in the right place
script_start = content.find('<script>')
if script_start > 0:
    print(f"\n✓ Script tag starts at position {script_start}")
