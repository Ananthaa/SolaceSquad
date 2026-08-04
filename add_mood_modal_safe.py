with open(r'c:\Anantha\Projects\Soul Squad\backend\templates\pages\user_dashboard.html', 'r', encoding='utf-8') as f:
    content = f.read()

# Find the {% endblock %} and insert before it
endblock_pos = content.rfind('{% endblock %}')

if endblock_pos == -1:
    print("ERROR: Could not find {% endblock %}")
    exit(1)

# Read the mood modal component
with open(r'c:\Anantha\Projects\Soul Squad\mood_modal_component.html', 'r', encoding='utf-8') as f:
    modal_code = f.read()

# Insert the modal before {% endblock %}
new_content = content[:endblock_pos] + '\n' + modal_code + '\n\n' + content[endblock_pos:]

# Write back
with open(r'c:\Anantha\Projects\Soul Squad\backend\templates\pages\user_dashboard.html', 'w', encoding='utf-8') as f:
    f.write(new_content)

print('Successfully added mood modal to user_dashboard.html')

# Verify
block_count = new_content.count('{% block')
endblock_count = new_content.count('{% endblock')
print(f'Block tags: {block_count}')
print(f'Endblock tags: {endblock_count}')

if block_count == 1 and endblock_count == 1:
    print('✓ Template structure is correct!')
else:
    print('✗ ERROR: Template structure is broken!')
    exit(1)
