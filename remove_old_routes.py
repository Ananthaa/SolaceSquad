"""Delete the old duplicate exercise routes properly"""

# Read the file
with open('backend/main.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Find and remove the old routes (lines with "OLD ROUTE - COMMENTED OUT")
new_lines = []
skip_mode = False

for i, line in enumerate(lines):
    if 'OLD ROUTE - COMMENTED OUT' in line:
        skip_mode = True
        continue
    
    # Stop skipping after we've passed the old routes section
    if skip_mode and line.strip() and not line.strip().startswith('#') and '@app.' in line:
        skip_mode = False
    
    if not skip_mode:
        new_lines.append(line)

# Write back
with open('backend/main.py', 'w', encoding='utf-8') as f:
    f.writelines(new_lines)

print(f"Removed old routes. File reduced from {len(lines)} to {len(new_lines)} lines")
