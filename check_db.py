import sqlite3

def check():
    conn = sqlite3.connect('reviews.db')
    cursor = conn.cursor()
    
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = cursor.fetchall()
    print(f"Tables found: {tables}")
    
    for table_name in [t[0] for t in tables]:
        cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
        count = cursor.fetchone()[0]
        print(f"Table '{table_name}' has {count} entries.")
        
    conn.close()

if __name__ == "__main__":
    check()
