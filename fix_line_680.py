with open('backend/templates/pages/call_room.html', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Fix line 680 (index 679) - add missing closing brace
if len(lines) > 679:
    lines[679] = lines[679].replace(
        '{{ appointment.user_id }',
        '{{ appointment.user_id }}'
    )

with open('backend/templates/pages/call_room.html', 'w', encoding='utf-8') as f:
    f.writelines(lines)

print('Fixed line 680')
