path = r'C:/Anantha/Projects/Soul Squad/backend/main.py'
with open(path, 'rb') as f:
    content = f.read()

old = b'@app.post("/api/appointments/{appointment_id}/cancel")\r\n\r\nasync def cancel_appointment'
new = b'@app.post("/api/appointments/{appointment_id}/cancel")\r\nasync def cancel_appointment'

if old in content:
    content = content.replace(old, new)
    with open(path, 'wb') as f:
        f.write(content)
    print('Fixed blank line issue!')
else:
    print('Pattern not found - no fix needed')
