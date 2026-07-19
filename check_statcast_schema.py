import sqlite3
import os
db_path = 'data/sportsquant_ai.db'
conn = sqlite3.connect(db_path)
cursor = conn.cursor()
cursor.execute('PRAGMA table_info(statcast);')
columns = cursor.fetchall()
print('Statcast table schema:')
for col in columns:
    print(f'  {col[1]} {col[2]} {"NOT NULL" if col[3] else "NULL"} {"PRIMARY KEY" if col[5] else ""}')
conn.close()