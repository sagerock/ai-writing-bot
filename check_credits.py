#!/usr/bin/env python3
"""
Quick credit checker script for RomaLume
Run this to check your current credit balance
"""
import firebase_admin
from firebase_admin import credentials, firestore
import os
import sys

def init_firebase():
    """Initialize Firebase with credentials"""
    try:
        # Try to get existing app
        app = firebase_admin.get_app()
    except ValueError:
        # Initialize new app
        cred_path = os.getenv('FIREBASE_CREDENTIALS_PATH', './firebase_credentials.json')
        if not os.path.exists(cred_path):
            print("❌ Firebase credentials not found!")
            print(f"Expected at: {cred_path}")
            print("Set FIREBASE_CREDENTIALS_PATH environment variable or place credentials at ./firebase_credentials.json")
            return None
        
        cred = credentials.Certificate(cred_path)
        app = firebase_admin.initialize_app(cred)
    
    return firestore.client()

def check_user_credits(user_id):
    """Check credits for a specific user"""
    db = init_firebase()
    if not db:
        return None
    
    try:
        user_ref = db.collection("users").document(user_id)
        user_doc = user_ref.get()
        
        if not user_doc.exists:
            print(f"❌ User {user_id} not found in database")
            return None
        
        user_data = user_doc.to_dict()
        credits = user_data.get("credits", "Not set")
        credits_used = user_data.get("credits_used", "Not set")
        
        print(f"✅ User: {user_id}")
        print(f"📊 Current Credits: {credits}")
        print(f"📈 Credits Used: {credits_used}")
        
        return credits
        
    except Exception as e:
        print(f"❌ Error checking credits: {e}")
        return None

def main():
    if len(sys.argv) != 2:
        print("Usage: python3 check_credits.py <user_id>")
        print("Get your user ID from the browser console or Firebase Auth")
        sys.exit(1)
    
    user_id = sys.argv[1]
    credits = check_user_credits(user_id)
    
    if credits is not None and credits <= 0:
        print("\n🔧 Your credits are at 0. This explains the error!")
        print("To fix this, you can:")
        print("1. Contact admin to add more credits")
        print("2. Use admin panel if you have access")
        print("3. Check the account page to see credit info")

if __name__ == "__main__":
    main()