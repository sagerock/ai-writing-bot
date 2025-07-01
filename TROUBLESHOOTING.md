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

## 2. Chat Controls Bar Takes Up Too Much Vertical Space (React/Frontend)

### Issue
The controls area above the chat window (model selector, creativity slider, search web, save/clear controls) is too tall, leaving less room for the chat content.

### Symptom
- Controls are stacked in two rows, each with their own padding/margin.
- The chat window is much shorter than it should be.

### Solution
**Combine all controls into a single horizontal flex bar and remove extra padding/margin.**

#### Steps:
1. **In your Chat component JSX:**
   - Render both `ChatControls` and `ArchiveControls` inside a single `<div className="chat-controls-bar">` with `display: flex; align-items: center; gap: 12px;`.
   - Example:
     ```jsx
     <div className="chat-controls-bar">
       <ChatControls ... />
       <ArchiveControls ... />
     </div>
     ```
2. **In your CSS:**
   - Add a rule for `.chat-controls-bar`:
     ```css
     .chat-controls-bar {
       display: flex;
       align-items: center;
       gap: 12px;
       width: 100%;
       padding: 0 8px;
       margin: 0;
       flex-wrap: nowrap;
       min-height: 0;
       background: #f8f9fa;
       border-bottom: 1px solid #e9ecef;
     }
     ```
   - Remove or minimize padding/margin from `.chat-controls`, `.archive-controls`, and any wrappers.
   - Make all control groups inline (`flex-direction: row`) and reduce gaps.

#### Result
- The controls bar is now a single, compact row.
- The chat window is much taller and uses all available space.
- The UI is cleaner and more efficient for users. 