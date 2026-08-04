with open(r'c:\Anantha\Projects\Soul Squad\backend\templates\pages\user_dashboard.html', 'r', encoding='utf-8') as f:
    lines = f.readlines()

with open(r'c:\Anantha\Projects\Soul Squad\mood_modal_component.html', 'r', encoding='utf-8') as modal:
    modal_code = modal.read()

# Insert before the last line ({% endblock %})
new_lines = lines[:-1] + ['\n' + modal_code + '\n'] + [lines[-1]]

with open(r'c:\Anantha\Projects\Soul Squad\backend\templates\pages\user_dashboard.html', 'w', encoding='utf-8') as f:
    f.writelines(new_lines)

print('Successfully added mood modal to user_dashboard.html')
print(f'Total lines before: {len(lines)}')
print(f'Total lines after: {len(new_lines)}')
