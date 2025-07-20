#!/usr/bin/env python3
"""
Credit Debugging Tool for RomaLume

This script helps debug credit balance issues by:
1. Checking user credit balances directly from Firestore
2. Testing database connectivity
3. Analyzing credit transactions and history
4. Providing admin tools to investigate and fix credit issues

Usage:
python debug_credits.py --user-id <user_id>
python debug_credits.py --all-users
python debug_credits.py --test-connectivity
"""

import os
import sys
import argparse
import json
from datetime import datetime
from typing import Optional, Dict, List

# Set DNS resolver before importing Firebase libraries
os.environ["GRPC_DNS_RESOLVER"] = "native"

import firebase_admin
from firebase_admin import credentials, firestore, auth as firebase_auth
from google.cloud.firestore_v1.transaction import Transaction


class CreditDebugger:
    def __init__(self):
        self.db = None
        self.initialize_firebase()

    def initialize_firebase(self):
        """Initialize Firebase Admin SDK"""
        try:
            # Check if service account file exists
            service_account_path = "firebase_service_account.json"
            if not os.path.exists(service_account_path):
                print(f"❌ ERROR: Firebase service account file not found: {service_account_path}")
                sys.exit(1)

            # Initialize Firebase if not already done
            if not firebase_admin._apps:
                cred = credentials.Certificate(service_account_path)
                firebase_admin.initialize_app(cred)
                print("✅ Firebase Admin SDK initialized")
            
            self.db = firestore.client()
            print("✅ Firestore client connected")
            
        except Exception as e:
            print(f"❌ ERROR: Failed to initialize Firebase: {e}")
            sys.exit(1)

    def test_firestore_connectivity(self) -> bool:
        """Test basic Firestore connectivity"""
        try:
            print("🔍 Testing Firestore connectivity...")
            
            # Test write
            test_ref = self.db.collection("debug_test").document("connectivity_test")
            test_data = {
                "timestamp": firestore.SERVER_TIMESTAMP,
                "test": "connectivity_check"
            }
            test_ref.set(test_data)
            print("✅ Write test passed")
            
            # Test read
            doc = test_ref.get()
            if doc.exists:
                print("✅ Read test passed")
                # Clean up test document
                test_ref.delete()
                print("✅ Delete test passed")
                return True
            else:
                print("❌ Read test failed")
                return False
                
        except Exception as e:
            print(f"❌ Firestore connectivity test failed: {e}")
            return False

    def get_user_credit_details(self, user_id: str) -> Dict:
        """Get detailed credit information for a user"""
        try:
            print(f"\n🔍 Analyzing credits for user: {user_id}")
            
            # Get user data from Firestore
            user_ref = self.db.collection("users").document(user_id)
            user_doc = user_ref.get()
            
            result = {
                "user_id": user_id,
                "firestore_exists": user_doc.exists,
                "credits": None,
                "credits_used": None,
                "firebase_auth_exists": False,
                "firebase_auth_data": None,
                "raw_firestore_data": None,
                "status": "unknown"
            }
            
            # Check Firebase Auth
            try:
                auth_user = firebase_auth.get_user(user_id)
                result["firebase_auth_exists"] = True
                result["firebase_auth_data"] = {
                    "email": auth_user.email,
                    "display_name": auth_user.display_name,
                    "email_verified": auth_user.email_verified,
                    "disabled": auth_user.disabled,
                    "custom_claims": auth_user.custom_claims
                }
                print(f"✅ User exists in Firebase Auth: {auth_user.email}")
            except Exception as e:
                print(f"❌ User not found in Firebase Auth: {e}")
            
            # Get Firestore data
            if user_doc.exists:
                firestore_data = user_doc.to_dict()
                result["raw_firestore_data"] = firestore_data
                result["credits"] = firestore_data.get("credits", "NOT_SET")
                result["credits_used"] = firestore_data.get("credits_used", "NOT_SET")
                
                credits = result["credits"]
                if credits == "NOT_SET":
                    result["status"] = "new_user_no_credits_field"
                elif isinstance(credits, (int, float)):
                    if credits <= 0:
                        result["status"] = "out_of_credits"
                    else:
                        result["status"] = "has_credits"
                else:
                    result["status"] = "invalid_credits_type"
                    
                print(f"📊 Firestore data found:")
                print(f"   Credits: {credits}")
                print(f"   Credits Used: {result['credits_used']}")
                print(f"   Status: {result['status']}")
            else:
                result["status"] = "no_firestore_document"
                print(f"❌ No Firestore document found for user")
            
            return result
            
        except Exception as e:
            print(f"❌ Error analyzing user credits: {e}")
            return {"error": str(e)}

    def simulate_credit_check(self, user_id: str) -> Dict:
        """Simulate the exact credit check logic from the main app"""
        try:
            print(f"\n🎯 Simulating credit check for user: {user_id}")
            
            user_ref = self.db.collection("users").document(user_id)
            transaction = self.db.transaction()
            
            @firestore.transactional
            def check_credits_simulation(transaction: Transaction, user_ref):
                user_snapshot = user_ref.get(transaction=transaction)
                
                if not user_snapshot.exists:
                    print("ℹ️  User document doesn't exist - would get 100 initial credits")
                    return {
                        "status": "new_user",
                        "would_get_credits": 99,  # 100 - 1 for the request
                        "credits_after": 99
                    }
                
                user_data = user_snapshot.to_dict()
                credits = user_data.get("credits", 0)
                
                if credits <= 0:
                    return {
                        "status": "insufficient_credits",
                        "current_credits": credits,
                        "error": "You have run out of credits."
                    }
                
                return {
                    "status": "sufficient_credits",
                    "current_credits": credits,
                    "credits_after": credits - 1
                }
            
            result = check_credits_simulation(transaction, user_ref)
            
            if result["status"] == "insufficient_credits":
                print(f"❌ Credit check would FAIL: {result['error']}")
                print(f"   Current credits: {result['current_credits']}")
            elif result["status"] == "sufficient_credits":
                print(f"✅ Credit check would PASS")
                print(f"   Current credits: {result['current_credits']}")
                print(f"   Credits after request: {result['credits_after']}")
            else:
                print(f"ℹ️  New user scenario: would get {result['would_get_credits']} credits")
            
            return result
            
        except Exception as e:
            print(f"❌ Credit check simulation failed: {e}")
            return {"error": str(e)}

    def fix_user_credits(self, user_id: str, new_credits: int) -> bool:
        """Fix user credits by setting them to a specific value"""
        try:
            print(f"\n🔧 Setting credits for user {user_id} to {new_credits}")
            
            user_ref = self.db.collection("users").document(user_id)
            user_ref.set({"credits": new_credits}, merge=True)
            
            print(f"✅ Credits updated successfully")
            
            # Verify the update
            updated_doc = user_ref.get()
            if updated_doc.exists:
                updated_credits = updated_doc.to_dict().get("credits", "ERROR")
                print(f"✅ Verified: User now has {updated_credits} credits")
                return updated_credits == new_credits
            else:
                print(f"❌ Failed to verify credit update")
                return False
                
        except Exception as e:
            print(f"❌ Failed to fix user credits: {e}")
            return False

    def get_all_users_credits(self, limit: int = 50) -> List[Dict]:
        """Get credit information for all users"""
        try:
            print(f"\n📊 Getting credit information for all users (limit: {limit})")
            
            users_list = []
            
            # Get users from Firebase Auth
            page = firebase_auth.list_users(max_results=limit)
            
            for user in page.users:
                credit_info = self.get_user_credit_details(user.uid)
                credit_info["email"] = user.email
                users_list.append(credit_info)
            
            # Summary
            total_users = len(users_list)
            users_with_credits = sum(1 for u in users_list if isinstance(u.get("credits"), (int, float)) and u["credits"] > 0)
            users_out_of_credits = sum(1 for u in users_list if isinstance(u.get("credits"), (int, float)) and u["credits"] <= 0)
            users_no_data = sum(1 for u in users_list if not u.get("firestore_exists"))
            
            print(f"\n📈 SUMMARY:")
            print(f"   Total users checked: {total_users}")
            print(f"   Users with credits: {users_with_credits}")
            print(f"   Users out of credits: {users_out_of_credits}")
            print(f"   Users with no Firestore data: {users_no_data}")
            
            return users_list
            
        except Exception as e:
            print(f"❌ Failed to get all users credits: {e}")
            return []

    def create_debug_report(self, user_id: Optional[str] = None) -> str:
        """Create a comprehensive debug report"""
        report = []
        report.append("=" * 60)
        report.append("ROMALUME CREDIT SYSTEM DEBUG REPORT")
        report.append("=" * 60)
        report.append(f"Generated at: {datetime.now().isoformat()}")
        report.append("")
        
        # Test connectivity
        connectivity_ok = self.test_firestore_connectivity()
        report.append(f"Firestore Connectivity: {'✅ OK' if connectivity_ok else '❌ FAILED'}")
        report.append("")
        
        if user_id:
            # Single user analysis
            report.append(f"SINGLE USER ANALYSIS: {user_id}")
            report.append("-" * 40)
            
            user_details = self.get_user_credit_details(user_id)
            report.append(f"User Details: {json.dumps(user_details, indent=2, default=str)}")
            report.append("")
            
            credit_check = self.simulate_credit_check(user_id)
            report.append(f"Credit Check Simulation: {json.dumps(credit_check, indent=2, default=str)}")
            
        else:
            # All users analysis
            report.append("ALL USERS ANALYSIS")
            report.append("-" * 40)
            
            all_users = self.get_all_users_credits()
            report.append(f"Total users analyzed: {len(all_users)}")
            
            # Group by status
            status_groups = {}
            for user in all_users:
                status = user.get("status", "unknown")
                if status not in status_groups:
                    status_groups[status] = []
                status_groups[status].append(user)
            
            report.append("\nUsers by status:")
            for status, users in status_groups.items():
                report.append(f"  {status}: {len(users)} users")
                if status == "out_of_credits":
                    report.append("    Users out of credits:")
                    for user in users[:5]:  # Show first 5
                        report.append(f"      - {user.get('email', 'no email')} (ID: {user['user_id']})")
                    if len(users) > 5:
                        report.append(f"      ... and {len(users) - 5} more")
        
        report_text = "\n".join(report)
        
        # Save report to file
        report_filename = f"credit_debug_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        with open(report_filename, 'w') as f:
            f.write(report_text)
        
        print(f"\n📋 Debug report saved to: {report_filename}")
        return report_text


def main():
    parser = argparse.ArgumentParser(description="Debug RomaLume credit system")
    parser.add_argument("--user-id", help="Debug specific user ID")
    parser.add_argument("--all-users", action="store_true", help="Analyze all users")
    parser.add_argument("--test-connectivity", action="store_true", help="Test database connectivity")
    parser.add_argument("--fix-credits", type=int, help="Fix user credits (requires --user-id)")
    parser.add_argument("--report", action="store_true", help="Generate debug report")
    
    args = parser.parse_args()
    
    if len(sys.argv) == 1:
        parser.print_help()
        return
    
    debugger = CreditDebugger()
    
    if args.test_connectivity:
        connectivity_ok = debugger.test_firestore_connectivity()
        if connectivity_ok:
            print("\n✅ Database connectivity is working properly")
        else:
            print("\n❌ Database connectivity issues detected")
    
    if args.user_id:
        if args.fix_credits is not None:
            success = debugger.fix_user_credits(args.user_id, args.fix_credits)
            if not success:
                print("❌ Failed to fix user credits")
        else:
            user_details = debugger.get_user_credit_details(args.user_id)
            credit_check = debugger.simulate_credit_check(args.user_id)
            
            print("\n" + "="*50)
            print("DIAGNOSIS:")
            if credit_check.get("status") == "insufficient_credits":
                print("❌ ISSUE FOUND: User is out of credits")
                print("💡 SOLUTION: Add credits using --fix-credits flag")
                print(f"   Example: python debug_credits.py --user-id {args.user_id} --fix-credits 100")
            elif credit_check.get("status") == "sufficient_credits":
                print("✅ CREDITS OK: User has sufficient credits")
                print("🤔 If user is still getting 'out of credits' error, check:")
                print("   1. Client-side caching issues")
                print("   2. API authentication issues")
                print("   3. Different user ID being used")
            else:
                print("ℹ️  NEW USER: User will get initial credits on first use")
    
    if args.all_users:
        all_users = debugger.get_all_users_credits()
        
        print("\n🔍 USERS WITH ISSUES:")
        problem_users = [u for u in all_users if u.get("status") in ["out_of_credits", "invalid_credits_type"]]
        
        if problem_users:
            for user in problem_users[:10]:  # Show first 10
                print(f"  - {user.get('email', 'no email')} (ID: {user['user_id']})")
                print(f"    Status: {user.get('status')}")
                print(f"    Credits: {user.get('credits')}")
                print()
        else:
            print("  No users with credit issues found!")
    
    if args.report:
        report = debugger.create_debug_report(args.user_id)


if __name__ == "__main__":
    main()