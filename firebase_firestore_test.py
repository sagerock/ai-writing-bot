import os
os.environ["GRPC_DNS_RESOLVER"] = "native"  # Force gRPC to use system DNS

import firebase_admin
from firebase_admin import credentials, firestore

# Initialize Firebase Admin
cred = credentials.Certificate("firebase_service_account.json")
if not firebase_admin._apps:
    firebase_admin.initialize_app(cred)

db = firestore.client()

# Test write
print("Writing test document...")
test_ref = db.collection("test_collection").document("test_doc")
test_ref.set({"hello": "world"})

# Test read
print("Reading test document...")
doc = test_ref.get()
if doc.exists:
    print("Success! Document data:", doc.to_dict())
else:
    print("Failed to read document.")

print("Done.")