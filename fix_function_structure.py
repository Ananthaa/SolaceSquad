import re

# Read the file
with open(r'c:\Anantha\Projects\Soul Squad\backend\templates\pages\call_room.html', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Find and fix the loadPatientHealthData function
# The try block should be indented inside the function
new_lines = []
i = 0
while i < len(lines):
    line = lines[i]
    
    # If we're at line 680 (the patientId line)
    if i == 679:  # 0-indexed, so line 680 is index 679
        new_lines.append(line)  # const patientId = {{ appointment.user_id }};
        i += 1
        # Skip empty lines
        while i < len(lines) and lines[i].strip() == '':
            i += 1
        # Now we should be at the try block - indent it properly
        if i < len(lines) and 'try {' in lines[i]:
            new_lines.append('\n')
            new_lines.append('        try {\n')  # Properly indented inside function
            i += 1
        continue
    
    new_lines.append(line)
    i += 1

# Write back
with open(r'c:\Anantha\Projects\Soul Squad\backend\templates\pages\call_room.html', 'w', encoding='utf-8') as f:
    f.writelines(new_lines)

print("Fixed loadPatientHealthData function structure!")
print("\nVerifying fix:")
with open(r'c:\Anantha\Projects\Soul Squad\backend\templates\pages\call_room.html', 'r', encoding='utf-8') as f:
    lines = f.readlines()
    for i in range(675, 695):
        print(f"{i+1}: {lines[i].rstrip()}")
