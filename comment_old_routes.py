"""Comment out the old duplicate exercise routes"""

# Read the file
with open('backend/main.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Comment out lines 4043-4165 (0-indexed: 4042-4164)
for i in range(4042, 4165):
    if i < len(lines) and not lines[i].strip().startswith('#'):
        # Add comment marker
        lines[i] = '# OLD ROUTE - COMMENTED OUT: ' + lines[i]

# Write back
with open('backend/main.py', 'w', encoding='utf-8') as f:
    f.writelines(lines)

print("Commented out old duplicate exercise routes (lines 4044-4166)")
