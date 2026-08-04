path = r'C:/Anantha/Projects/Soul Squad/backend/templates/pages/call_room.html'
with open(path, 'rb') as f:
    content = f.read()

old = b'    user_id: { { appointment.user_id } }'
new = b'        user_id: {{ appointment.user_id }}'

if old in content:
    content = content.replace(old, new)
    with open(path, 'wb') as f:
        f.write(content)
    print('FIXED: call_room.html broken Jinja2 tag')
else:
    # Verify it's already clean
    if b'user_id: {{ appointment.user_id }}' in content:
        print('Already fixed - Jinja2 tag is clean')
    else:
        print('WARNING: unexpected state - searching for user_id line...')
        lines = content.split(b'\n')
        for i, line in enumerate(lines, 1):
            if b'user_id' in line and b'appointment' in line:
                print(f'L{i}: {repr(line)}')
