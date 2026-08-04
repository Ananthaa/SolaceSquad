with open(r'c:\Anantha\Projects\Soul Squad\backend\templates\pages\user_dashboard.html', 'r', encoding='utf-8') as f:
    lines = f.readlines()

with open(r'c:\Anantha\Projects\Soul Squad\mood_modal_component.html', 'r', encoding='utf-8') as modal:
    modal_code = modal.read()

# Insert before line 543 (the {% endblock %} line)
# lines[0:542] + modal + lines[542:]
new_lines = lines[:542] + ['\n' + modal_code + '\n\n'] + lines[542:]

with open(r'c:\Anantha\Projects\Soul Squad\backend\templates\pages\user_dashboard.html', 'w', encoding='utf-8') as f:
    f.writelines(new_lines)

print('Successfully added mood modal to user_dashboard.html')
print(f'Total lines before: {len(lines)}')
print(f'Total lines after: {len(new_lines)}')

# Verify
with open(r'c:\Anantha\Projects\Soul Squad\backend\templates\pages\user_dashboard.html', 'r', encoding='utf-8') as f:
    content = f.read()
    block_count = content.count('{% block')
    endblock_count = content.count('{% endblock')
    print(f'\nVerification:')
    print(f'  block count: {block_count}')
    print(f'  endblock count: {endblock_count}')
    print(f'  Should both be 1')
    if block_count == 1 and endblock_count == 1:
        print('  SUCCESS!')
    else:
        print('  ERROR: Mismatch!')
