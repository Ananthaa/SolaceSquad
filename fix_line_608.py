with open(r'c:\Anantha\Projects\Soul Squad\backend\templates\pages\call_room.html', 'r', encoding='utf-8') as f:
    content = f.read()

# Fix the broken Jinja2 template on line 608
content = content.replace('user_id: { { appointment.user_id } }', 'user_id: {{ appointment.user_id }}')

with open(r'c:\Anantha\Projects\Soul Squad\backend\templates\pages\call_room.html', 'w', encoding='utf-8') as f:
    f.write(content)

print("Fixed line 608!")
print("\nVerifying fix:")
with open(r'c:\Anantha\Projects\Soul Squad\backend\templates\pages\call_room.html', 'r', encoding='utf-8') as f:
    lines = f.readlines()
    for i in range(605, 612):
        print(f"{i+1}: {lines[i].rstrip()}")
