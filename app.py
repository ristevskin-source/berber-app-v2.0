Dodato Streamlit korisnicko sucelje
from database import inicijalizuj_bazu

inicijalizuj_bazu()

print("Baza uspešno kreirana")
import sqlite3

conn = sqlite3.connect("salon.db")
c = conn.cursor()

c.execute("""
SELECT name FROM sqlite_master 
WHERE type='table'
""")

print(c.fetchall())

conn.close()
