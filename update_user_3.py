#!/usr/bin/env python3
"""
Script to update user ID 3 to enterprise plan
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy.orm import Session
from app.db.base import get_db
from app.db import crud, models

def update_user_to_enterprise(user_id: int):
    """
    Update specific user to enterprise plan
    """
    db = next(get_db())
    try:
        # Find user by ID
        user = crud.get_user(db, user_id=user_id)
        if not user:
            print(f"User with ID {user_id} not found")
            return False
        
        print(f"Found user: ID={user.id}, Email={user.email}, Current Plan={user.subscription_plan}")
        
        # Update subscription plan
        user.subscription_plan = "enterprise"
        db.commit()
        db.refresh(user)
        
        print(f"Successfully updated user {user.email} (ID: {user.id}) to enterprise plan")
        print(f"User now has unlimited video credits and magic commands")
        return True
        
    except Exception as e:
        print(f"Error updating subscription: {e}")
        db.rollback()
        return False
    finally:
        db.close()

if __name__ == "__main__":
    print("Updating User ID 3 to Enterprise Plan")
    print("======================================")
    
    success = update_user_to_enterprise(3)
    
    if success:
        print("\n✅ SUCCESS! User ID 3 now has enterprise plan with unlimited uploads")
    else:
        print("\n❌ Failed to update user")