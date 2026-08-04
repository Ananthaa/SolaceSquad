import re, os

# ============================================================
# FIX 1: call_room.html line 608 – broken Jinja2 tag
# ============================================================
call_room_path = r'C:/Anantha/Projects/Soul Squad/backend/templates/pages/call_room.html'
with open(call_room_path, 'rb') as f:
    content = f.read()

old = b'    user_id: { { appointment.user_id } }'
new = b'        user_id: {{ appointment.user_id }}'

if old in content:
    content = content.replace(old, new)
    with open(call_room_path, 'wb') as f:
        f.write(content)
    print('[FIXED] call_room.html: broken Jinja2 tag on line 608')
else:
    print('[OK]    call_room.html: Jinja2 tag already fixed (or pattern changed)')

# ============================================================
# FIX 2: vitals.html – degree symbol encoding + emoji issues
# ============================================================
vitals_path = r'C:/Anantha/Projects/Soul Squad/backend/templates/pages/vitals.html'
with open(vitals_path, 'rb') as f:
    raw = f.read()

print(f'\nVitals file encoding check:')
# Find the problematic sequences
issues = []
for pattern, fix, desc in [
    (b'\xc2\xb0',  b'&deg;',  'UTF-8 degree sign °'),
    (b'\xb0',      b'&deg;',  'Latin-1 degree sign °'),
    (b'\xc2\xb0F', b'&deg;F', 'degree F sequence'),
]:
    if pattern in raw:
        issues.append((pattern, fix, desc))
        print(f'  Found: {desc}')

for pat, fix, desc in issues:
    raw = raw.replace(pat, fix)

# Also find emoji that are corrupted - look for multi-byte sequences that might be emoji
# The "ðŸ"" pattern is UTF-8 emoji being read incorrectly - find heading with emoji
lines = raw.decode('utf-8', errors='replace').split('\n')
fixed_lines = []
for i, line in enumerate(lines):
    # Fix garbled UTF-8 emoji in page title / headings
    # These appear as things like "ðŸ¤–" or "ðŸ'""
    if '\ufffd' in line or 'Â' in line:
        print(f'  Potential garbled char on L{i+1}: {repr(line[:100])}')
    fixed_lines.append(line)

text = '\n'.join(fixed_lines)

with open(vitals_path, 'wb') as f:
    f.write(text.encode('utf-8'))

if issues:
    print('[FIXED] vitals.html: degree symbol encoding corrected')
else:
    print('[OK]    vitals.html: no byte-level degree issues found')

# ============================================================
# FIX 3: Look for mood tracker popup and check if it's hidden
# ============================================================
dashboard_path = r'C:/Anantha/Projects/Soul Squad/backend/templates/pages/dashboard.html'
if os.path.exists(dashboard_path):
    with open(dashboard_path, 'r', encoding='utf-8', errors='replace') as f:
        dash = f.read()
    # Check for mood popup
    if 'mood' in dash.lower():
        mood_lines = [(i+1, l) for i,l in enumerate(dash.split('\n')) 
                      if 'mood' in l.lower() and ('popup' in l.lower() or 'modal' in l.lower() or 'overlay' in l.lower())]
        print(f'\nMood popup references in dashboard.html:')
        for ln, l in mood_lines[:10]:
            print(f'  L{ln}: {l.strip()[:100]}')
    else:
        print('\n[WARN] No mood references in dashboard.html')
else:
    # Check user dashboard
    for fname in ['user_dashboard.html', 'home.html', 'index.html']:
        p = f'C:/Anantha/Projects/Soul Squad/backend/templates/pages/{fname}'
        if os.path.exists(p):
            print(f'\nFound: {fname}')
            break

print('\nDone!')
