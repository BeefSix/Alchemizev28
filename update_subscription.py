#!/usr/bin/env python3
"""
Script to create user account and update subscription plan to remove upload limits
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy.orm import Session
from app.db.base import get_db
from app.db import crud, models
from app.core.config import settings
from app.core.security_utils import get_password_hash

def create_user_with_enterprise_plan(email: str, password: str, full_name: str = None):
    """
    Create a new user with enterprise plan (unlimited uploads)
    """
    db = next(get_db())
    try:
        # Check if user already exists
        existing_user = crud.get_user_by_email(db, email=email)
        if existing_user:
            print(f"User {email} already exists. Updating to enterprise plan...")
            existing_user.subscription_plan = "enterprise"
            db.commit()
            db.refresh(existing_user)
            print(f"Successfully updated {email} to enterprise plan")
            return existing_user
        
        # Create new user with enterprise plan
        hashed_password = get_password_hash(password)
        new_user = models.User(
            email=email,
            hashed_password=hashed_password,
            full_name=full_name,
            subscription_plan="enterprise",  # Set to enterprise immediately
            is_active=True
        )
        
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        
        print(f"Successfully created user {email} with enterprise plan")
        print(f"User now has unlimited video credits and magic commands")
        return new_user
        
    except Exception as e:
        print(f"Error creating/updating user: {e}")
        db.rollback()
        return None
    finally:
        db.close()

def update_user_subscription(email: str, plan: str = "enterprise"):
    """
    Update user subscription plan to remove limits
    """
    db = next(get_db())
    try:
        # Find user by email
        user = crud.get_user_by_email(db, email=email)
        if not user:
            print(f"User with email {email} not found")
            return False
        
        # Update subscription plan
        user.subscription_plan = plan
        db.commit()
        db.refresh(user)
        
        print(f"Successfully updated user {email} to {plan} plan")
        print(f"User now has unlimited video credits and magic commands")
        return True
        
    except Exception as e:
        print(f"Error updating subscription: {e}")
        db.rollback()
        return False
    finally:
        db.close()

def list_users():
    """
    List all users in the database
    """
    db = next(get_db())
    try:
        users = db.query(models.User).all()
        print("\nAll users in database:")
        for user in users:
            print(f"ID: {user.id}, Email: {user.email}, Plan: {user.subscription_plan}")
    except Exception as e:
        print(f"Error listing users: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    print("User Account Creator & Subscription Updater")
    print("===========================================")
    
    # Create your account with enterprise plan
    email = "Merlino874@gmail.com"
    password = "SecurePassword123!"  # You can change this
    full_name = "Merlino"
    
    print(f"\nCreating/updating account for {email}...")
    user = create_user_with_enterprise_plan(email, password, full_name)
    
    if user:
        print("\n✅ SUCCESS! Your account now has:")
        print("- Unlimited video credits")
        print("- Unlimited magic commands")
        print("- All premium features")
        print("- No upload limits")
        print(f"\nYou can now login with:")
        print(f"Email: {email}")
        print(f"Password: {password}")
    else:
        print("\n❌ Failed to create/update account")
    
    # List all users to confirm
    list_users()