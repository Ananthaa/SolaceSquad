"""Fix the missing func import in main.py"""

# Read the file
with open('backend/main.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Find and fix the line
for i, line in enumerate(lines):
    if i == 3936 and '"""Video Library - Folders View"""' in line:
        # Insert the import after this line
        lines.insert(i + 1, '    from sqlalchemy import func\n')
        break

# Write back
with open('backend/main.py', 'w', encoding='utf-8') as f:
    f.writelines(lines)

print("Fixed! Added 'from sqlalchemy import func' at line 3938")
