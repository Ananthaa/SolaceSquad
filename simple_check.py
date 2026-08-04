with open(r'c:\Anantha\Projects\Soul Squad\backend\templates\pages\call_room.html', 'r', encoding='utf-8') as f:
    content = f.read()

print('1. showConsentModal function found:', 'function showConsentModal()' in content)
print('2. onclick attribute found:', 'onclick="showConsentModal()"' in content or "onclick='showConsentModal()'" in content)
print('3. patientId with closing braces:', 'const patientId = {{ appointment.user_id }};' in content)
print('4. Script tag found:', '<script>' in content)

# Find the button line
lines = content.split('\n')
for i, line in enumerate(lines, 1):
    if 'Join Call' in line and 'button' in line.lower():
        print(f'\n5. Join Call button at line {i}:')
        print(f'   {line.strip()}')
        # Check previous line for onclick
        if i > 1:
            print(f'   Previous line: {lines[i-2].strip()}')
        break

# Check if showConsentModal is defined
for i, line in enumerate(lines, 1):
    if 'function showConsentModal()' in line:
        print(f'\n6. showConsentModal defined at line {i}')
        for j in range(i-1, min(i+5, len(lines))):
            print(f'   {j+1}: {lines[j].rstrip()}')
        break
