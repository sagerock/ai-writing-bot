import firebase_admin
from firebase_admin import credentials, auth
import sys

# --- Configuration ---
# The path to your Firebase service account key
SERVICE_ACCOUNT_KEY_PATH = "firebase_service_account.json"

# --- Script Logic ---
def make_admin_by_email(email: str):
    """Set admin privileges for a user by their email address."""
    try:
        if not firebase_admin._apps:
            cred = credentials.Certificate(SERVICE_ACCOUNT_KEY_PATH)
            firebase_admin.initialize_app(cred)

        # Look up user by email
        user = auth.get_user_by_email(email)
        print(f"Found user: {user.uid} ({user.email})")

        # Set the custom claim 'admin' to True for the specified user
        auth.set_custom_user_claims(user.uid, {'admin': True})

        print(f"✅ Successfully set admin privileges for user: {email}")

        # Verify the claim was set
        user = auth.get_user(user.uid)
        print(f"Current claims for user: {user.custom_claims}")

    except auth.UserNotFoundError:
        print(f"❌ No user found with email: {email}")
    except Exception as e:
        print(f"❌ An error occurred: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python set_admin.py <email>")
        print("Example: python set_admin.py user@example.com")
        sys.exit(1)

    email = sys.argv[1]
    make_admin_by_email(email) 