# Credit System Debugging Guide for RomaLume

This guide helps you diagnose and fix credit-related issues in the RomaLume application.

## Quick Diagnosis Checklist

When a user reports "out of credits" issues:

1. **Get the user's ID** from Firebase Auth console or admin panel
2. **Use the debug tools** to investigate the issue
3. **Apply the appropriate fix** based on the diagnosis

## Available Debugging Tools

### 1. Command Line Debug Script

**Location**: `/debug_credits.py`

**Basic Usage**:
```bash
# Debug a specific user
python debug_credits.py --user-id "USER_ID_HERE"

# Check all users for credit issues
python debug_credits.py --all-users

# Test database connectivity
python debug_credits.py --test-connectivity

# Generate comprehensive report
python debug_credits.py --report

# Fix a user's credits (emergency)
python debug_credits.py --user-id "USER_ID_HERE" --fix-credits 100
```

**What it does**:
- Checks Firestore connectivity
- Analyzes user documents in detail
- Simulates the exact credit check logic from the app
- Provides specific diagnosis and recommendations
- Can fix credits if needed

### 2. Admin API Debug Endpoints

These endpoints are available through the web interface for admins:

**Debug specific user**:
```
GET /admin/debug/user/{user_id}/credits
```

**Get credits summary for all users**:
```
GET /admin/debug/credits/summary
```

**Emergency fix user credits**:
```
POST /admin/debug/user/{user_id}/fix-credits?credit_amount=100
```

### 3. Existing Admin Panel

**Location**: `https://yourapp.com/admin` (requires admin privileges)

Features:
- View all users and their credit balances
- Update user credits manually
- See credit usage statistics

## Common Issues and Solutions

### Issue 1: User Shows 0 Credits But Should Have More

**Symptoms**: User reports "out of credits" but admin panel shows they have credits

**Diagnosis**:
```bash
python debug_credits.py --user-id "USER_ID"
```

**Likely Causes**:
- Client-side caching issues
- User logged in with different account
- Database replication lag

**Solutions**:
1. Have user clear browser cache and reload
2. Verify user is logged into correct account
3. Check if credits show correctly in admin panel
4. Use API debug endpoint to get real-time data

### Issue 2: User Document Doesn't Exist

**Symptoms**: New user gets "out of credits" on first use

**Diagnosis**: Debug script will show "no_firestore_document" status

**Causes**:
- Database connectivity issues during first use
- Firebase transaction failures
- User hasn't actually made a request yet

**Solutions**:
1. Test database connectivity: `python debug_credits.py --test-connectivity`
2. Have user try again (should create document with 100 credits)
3. Manually create user document with initial credits

### Issue 3: Credits Field Has Wrong Data Type

**Symptoms**: Credits show as string/null instead of number

**Diagnosis**: Debug script will show "invalid_credits_type" status

**Solution**:
```bash
python debug_credits.py --user-id "USER_ID" --fix-credits 100
```

### Issue 4: Widespread Credit Issues

**Symptoms**: Multiple users reporting credit problems

**Diagnosis**:
```bash
python debug_credits.py --all-users
```

**Check for**:
- Database connectivity problems
- Recent code changes affecting credit logic
- Firebase service outages

## Emergency Procedures

### Quick Fix for Single User
```bash
# Method 1: Command line
python debug_credits.py --user-id "USER_ID" --fix-credits 100

# Method 2: API endpoint (requires admin token)
curl -X POST "https://yourapi.com/admin/debug/user/USER_ID/fix-credits?credit_amount=100" \
     -H "Authorization: Bearer ADMIN_TOKEN"
```

### Batch Fix for Multiple Users
```bash
# Get list of affected users
python debug_credits.py --all-users > users_report.txt

# Fix each user individually (manual process for safety)
python debug_credits.py --user-id "USER_ID_1" --fix-credits 100
python debug_credits.py --user-id "USER_ID_2" --fix-credits 100
```

## Monitoring and Prevention

### Regular Health Checks
```bash
# Weekly credit system check
python debug_credits.py --all-users --report
```

### Key Metrics to Monitor
- Number of users with 0 credits
- Users without Firestore documents
- Credit transaction failures
- Database connectivity issues

### Log Analysis
Check server logs for:
- `HTTPException(status_code=402, detail="You have run out of credits.")`
- Firestore connection errors
- Transaction failures in `check_and_update_credits`

## Getting User ID for Debugging

### From Admin Panel
1. Go to admin panel
2. Find user by email
3. Copy their UID

### From Firebase Console
1. Open Firebase Console
2. Go to Authentication > Users
3. Find user and copy UID

### From Browser Debug Console (if user is logged in)
```javascript
// Have user run this in browser console
firebase.auth().currentUser.uid
```

## Understanding the Credit System

### How Credits Work
1. **New users**: Get 100 credits on first request
2. **Each request**: Costs 1 credit
3. **Credit check**: Happens before processing each request
4. **Transaction**: Ensures atomic credit deduction

### Database Structure
```
/users/{user_id}
{
  "credits": 42,           // Current credit balance
  "credits_used": 58,      // Total credits used
  // ... other user data
}
```

### Credit Check Logic
```python
# Simplified version of the check
if not user_exists:
    create_user_with_100_credits()
elif user.credits <= 0:
    return "out of credits"
else:
    deduct_1_credit()
    proceed_with_request()
```

## Troubleshooting Checklist

- [ ] User ID is correct
- [ ] User exists in Firebase Auth
- [ ] User document exists in Firestore
- [ ] Credits field is a number (not string/null)
- [ ] Credits value is positive
- [ ] Database connectivity is working
- [ ] No recent code changes affecting credits
- [ ] User is logged into correct account
- [ ] No client-side caching issues

## Support Contacts

For complex credit system issues:
1. Check this guide first
2. Run debug scripts to gather data
3. Document findings and attempted solutions
4. Escalate with detailed debug information