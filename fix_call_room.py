import re

# Read the file with different encoding
with open('backend/templates/pages/call_room.html', 'r', encoding='utf-8-sig', errors='ignore') as f:
    content = f.read()

# Simple string replacement
old_text = '''    };

    try {'''

new_text = '''

        try {'''

# Replace
content = content.replace(old_text, new_text)

# Write back
with open('backend/templates/pages/call_room.html', 'w', encoding='utf-8') as f:
    f.write(content)

print("Fixed!")
