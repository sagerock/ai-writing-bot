# Project Troubleshooting Guide

This document contains a list of common issues encountered during the development of this project and their solutions.

## 1. Firebase/Firestore Connection Timeouts in FastAPI

### Issue
The main FastAPI application fails to connect to Google Cloud services like Firebase Firestore, resulting in timeout errors. However, a separate, minimal Python script using the same credentials and service account file can connect successfully.

### Symptom
- The application hangs and eventually throws a timeout error when making its first call to Firestore (e.g., `db.collection(...).get()`).
- Error messages might include `Deadline Exceeded`, `unavailable`, or other network-related gRPC errors.

### Root Cause
The Google Cloud Python libraries (including `firebase-admin`) use `gRPC` for communication. By default, gRPC uses its own internal DNS resolver (C-ares). This resolver can sometimes fail to resolve Google's service hostnames correctly within the complex asynchronous environment of a web application framework like FastAPI, or within certain network configurations (e.g., specific Docker networking, VPNs).

The simple test script works because, in its minimal environment, it often falls back to the system's standard (native) DNS resolver, which functions correctly.

### Solution
Force the `gRPC` library to use the operating system's native DNS resolver instead of its own. This is achieved by setting an environment variable at the very top of the application's entry point, before any Google or Firebase libraries are imported.

**In `main.py`:**

```python
import os

# This line MUST come before any firebase_admin or google.cloud imports.
os.environ["GRPC_DNS_RESOLVER"] = "native"

import firebase_admin
# ... rest of your application imports and code
```

By setting this environment variable, you ensure that all subsequent gRPC calls from the Firebase SDK will use the more reliable system DNS, resolving the connection issue. 