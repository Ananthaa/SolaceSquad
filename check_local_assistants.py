import sqlite3
conn = sqlite3.connect(r'c:\Anantha\Projects\Soul Squad\soul_squad.db')
cur = conn.cursor()
cur.execute("SELECT id, name, email, user_type FROM users WHERE user_type IN ('admin_assistant','assistant') ORDER BY id")
rows = cur.fetchall()
if rows:
    print('Assistant accounts found:')
    for r in rows:
        print(f'  ID={r[0]}  name={r[1]}  email={r[2]}  type={r[3]}')
else:
    print('No assistant accounts in local DB. Showing all users:')
    cur.execute("SELECT id, name, email, user_type FROM users ORDER BY id LIMIT 30")
    for r in cur.fetchall():
        print(f'  ID={r[0]}  name={r[1]}  email={r[2]}  type={r[3]}')
conn.close()
