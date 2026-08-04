import re

# Read the file
with open('backend/templates/pages/call_room.html', 'r', encoding='latin-1') as f:
    content = f.read()

# Add updateStatus call after joining room
old_code = '''            socket.on('room_joined', (data) => {
                console.log('Joined room:', data);'''

new_code = '''            socket.on('room_joined', (data) => {
                console.log('Joined room:', data);
                updateStatus('connected', 'Connected');'''

content = content.replace(old_code, new_code)

# Write back
with open('backend/templates/pages/call_room.html', 'w', encoding='utf-8') as f:
    f.write(content)

print("Added updateStatus call to room_joined event!")
