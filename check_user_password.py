import sqlite3
from passlib.context import CryptContext

def check_and_update_user():
    conn = sqlite3.connect('alchemize.db')
    cursor = conn.cursor()
    
    # Check if user exists
    cursor.execute('SELECT id, email, hashed_password FROM users WHERE email = ?', ('merlino874@gmail.com',))
    row = cursor.fetchone()
    
    if row:
        user_id, email, hashed_password = row
        print(f"User found: {email}")
        print(f"Has password: {bool(hashed_password)}")
        
        # Update password to a known value
        pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
        new_password = "TestPassword123!"
        new_hashed = pwd_context.hash(new_password)
        
        cursor.execute('UPDATE users SET hashed_password = ? WHERE id = ?', (new_hashed, user_id))
        conn.commit()
        
        print(f"✅ Password updated for {email}")
        print(f"New password: {new_password}")
        
    else:
        print("❌ User merlino874@gmail.com not found")
    
    conn.close()

if __name__ == "__main__":
    check_and_update_user()