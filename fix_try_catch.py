import re

# Read the file
with open('backend/templates/pages/call_room.html', 'r', encoding='latin-1') as f:
    content = f.read()

# Find the loadPatientHealthData function and fix it
# The issue is the try block is not properly closed before catch

# Find and replace the broken structure
old_pattern = r'''        \}
    \} catch \(error\) \{
        console\.error\('Error fetching health data:', error\);
        document\.getElementById\('vitals-loading'\)\.textContent = 'Error loading data';
        document\.getElementById\('mood-loading'\)\.textContent = 'Error loading data';
    \}
    \}'''

new_pattern = '''        }
        } catch (error) {
            console.error('Error fetching health data:', error);
            document.getElementById('vitals-loading').textContent = 'Error loading data';
            document.getElementById('mood-loading').textContent = 'Error loading data';
        }
    }'''

content = content.replace(old_pattern, new_pattern)

# Write back
with open('backend/templates/pages/call_room.html', 'w', encoding='utf-8') as f:
    f.write(content)

print("Fixed loadPatientHealthData function!")
