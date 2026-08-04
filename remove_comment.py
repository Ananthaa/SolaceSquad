with open(r'c:\Anantha\Projects\Soul Squad\mood_modal_component.html', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Remove the comment line
new_lines = [line for line in lines if 'Add this before' not in line]

with open(r'c:\Anantha\Projects\Soul Squad\mood_modal_component.html', 'w', encoding='utf-8') as f:
    f.writelines(new_lines)

print('Removed comment line from mood modal component')
