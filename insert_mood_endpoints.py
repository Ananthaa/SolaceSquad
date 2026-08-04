with open(r'c:\Anantha\Projects\Soul Squad\backend\main.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

with open(r'c:\Anantha\Projects\Soul Squad\mood_api_endpoints.py', 'r', encoding='utf-8') as api:
    new_code = api.read()

# Insert after line 678 (after the get_latest_mood endpoint)
new_lines = lines[:678] + ['\n' + new_code + '\n\n'] + lines[678:]

with open(r'c:\Anantha\Projects\Soul Squad\backend\main.py', 'w', encoding='utf-8') as f:
    f.writelines(new_lines)

print('Successfully added mood API endpoints to main.py')
print(f'Total lines before: {len(lines)}')
print(f'Total lines after: {len(new_lines)}')
