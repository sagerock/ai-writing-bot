import firebase_admin
from firebase_admin import credentials, auth
import os

# --- Configuration ---
# IMPORTANT: Replace with the UID of the user you want to make an admin.
# You can find the UID in the Firebase Console under Authentication > Users.
USER_UID_TO_MAKE_ADMIN = "vFnc0maQZWaKjRcAohz8KIwLPED2"

# The path to your Firebase service account key
SERVICE_ACCOUNT_KEY_PATH = "firebase_service_account.json"

# --- Script Logic ---
if USER_UID_TO_MAKE_ADMIN == "REPLACE_WITH_THE_USER_UID":
    print("Please edit the script and replace 'REPLACE_WITH_THE_USER_UID' with a real User UID.")
else:
    try:
        cred = credentials.Certificate(SERVICE_ACCOUNT_KEY_PATH)
        firebase_admin.initialize_app(cred)

        # Set the custom claim 'admin' to True for the specified user
        auth.set_custom_user_claims(USER_UID_TO_MAKE_ADMIN, {'admin': True})

        print(f"✅ Successfully set admin privileges for user: {USER_UID_TO_MAKE_ADMIN}")
        
        # Optional: Verify the claim was set
        user = auth.get_user(USER_UID_TO_MAKE_ADMIN)
        print(f"Current claims for user: {user.custom_claims}")

    except Exception as e:
        print(f"❌ An error occurred: {e}") 