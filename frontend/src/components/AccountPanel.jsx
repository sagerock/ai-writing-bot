import React, { useState, useEffect } from 'react';
import { 
    updateProfile, 
    updateEmail, 
    updatePassword, 
    reauthenticateWithCredential, 
    EmailAuthProvider 
} from 'firebase/auth';
import { API_URL } from '../apiConfig';

const AccountPanel = ({ auth }) => {
    const [displayName, setDisplayName] = useState(auth.currentUser?.displayName || '');
    const [newEmail, setNewEmail] = useState(auth.currentUser?.email || '');
    const [newPassword, setNewPassword] = useState('');
    const [currentPassword, setCurrentPassword] = useState('');
    
    const [credits, setCredits] = useState(null);
    const [emailPreferences, setEmailPreferences] = useState({
        feature_updates: true,
        bug_fixes: true,
        pricing_changes: true,
        usage_tips: true
    });
    const [error, setError] = useState('');
    const [success, setSuccess] = useState('');
    const [needsReauth, setNeedsReauth] = useState(null); // 'email' or 'password'

    useEffect(() => {
        const fetchCredits = async () => {
            if (!auth.currentUser) return;
            try {
                const token = await auth.currentUser.getIdToken();
                const response = await fetch(`${API_URL}/user/credits`, {
                    headers: {
                        'Authorization': `Bearer ${token}`
                    }
                });
                if (!response.ok) {
                    throw new Error('Failed to fetch credits.');
                }
                const data = await response.json();
                setCredits(data.credits);
            } catch (err) {
                setError('Could not load credit balance.');
                console.error(err);
            }
        };

        const fetchEmailPreferences = async () => {
            if (!auth.currentUser) return;
            try {
                const token = await auth.currentUser.getIdToken();
                const response = await fetch(`${API_URL}/user/email-preferences`, {
                    headers: {
                        'Authorization': `Bearer ${token}`
                    }
                });
                if (!response.ok) {
                    throw new Error('Failed to fetch email preferences.');
                }
                const data = await response.json();
                setEmailPreferences(data);
            } catch (err) {
                console.error('Could not load email preferences:', err);
            }
        };

        fetchCredits();
        fetchEmailPreferences();
    }, [auth.currentUser]);

    const handleActionRequiringReauth = async (action) => {
        setError('');
        setSuccess('');

        if (action === 'email' && newEmail === auth.currentUser.email) {
            setError('This is already your current email.');
            return;
        }
        if (action === 'password' && newPassword.length < 6) {
            setError('Password must be at least 6 characters long.');
            return;
        }

        try {
            if (action === 'email') await updateEmail(auth.currentUser, newEmail);
            if (action === 'password') await updatePassword(auth.currentUser, newPassword);
            
            setSuccess(action === 'email' ? 'Email update process started. Check your new email to verify.' : 'Password updated successfully!');
            setNewPassword('');

        } catch (err) {
            if (err.code === 'auth/requires-recent-login') {
                setNeedsReauth(action);
                setError(`For security, please enter your current password to change your ${action}.`);
            } else {
                setError(`Failed to update ${action}. ${err.message}`);
                console.error(err);
            }
        }
    };
    
    const handleReauthAndRetry = async (e) => {
        e.preventDefault();
        if (!currentPassword) {
            setError('Please enter your current password.');
            return;
        }
        
        try {
            const user = auth.currentUser;
            const credential = EmailAuthProvider.credential(user.email, currentPassword);
            await reauthenticateWithCredential(user, credential);
            
            const actionToRetry = needsReauth;
            setNeedsReauth(null);
            setCurrentPassword('');
            await handleActionRequiringReauth(actionToRetry);

        } catch (err) {
            setError('Re-authentication failed. Please check your password.');
            console.error(err);
        }
    };

    const handleUpdateProfile = async (e) => {
        e.preventDefault();
        setError('');
        setSuccess('');
        try {
            await updateProfile(auth.currentUser, { displayName });
            setSuccess('Name updated successfully!');
        } catch (err) {
            setError('Failed to update name.');
            console.error(err);
        }
    };

    const handleEmailPreferencesUpdate = async (e) => {
        e.preventDefault();
        setError('');
        setSuccess('');
        try {
            const token = await auth.currentUser.getIdToken();
            const response = await fetch(`${API_URL}/user/email-preferences`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${token}`
                },
                body: JSON.stringify(emailPreferences)
            });
            if (!response.ok) {
                throw new Error('Failed to update email preferences.');
            }
            setSuccess('Email preferences updated successfully!');
        } catch (err) {
            setError('Failed to update email preferences.');
            console.error(err);
        }
    };

    if (needsReauth) {
        return (
            <div className="account-form-container">
                <h3>Re-authenticate to Continue</h3>
                {error && <p className="error" style={{textAlign: 'center'}}>{error}</p>}
                <form onSubmit={handleReauthAndRetry} className="account-form">
                    <label>Current Password:</label>
                    <input 
                        type="password"
                        value={currentPassword}
                        onChange={(e) => setCurrentPassword(e.target.value)}
                        autoFocus
                    />
                    <button type="submit">Confirm Password</button>
                    <button type="button" onClick={() => { setNeedsReauth(null); setError(''); }}>Cancel</button>
                </form>
            </div>
        );
    }

    return (
        <div className="account-form-container">
            <h2>My Account</h2>
            
            {error && <p className="error">{error}</p>}
            {success && <p className="success">{success}</p>}

            <div className="account-credits">
                <h3>Your Credits</h3>
                {credits !== null ? (
                    <p>You have <strong>{credits}</strong> credits remaining.</p>
                ) : (
                    <p>Loading credits...</p>
                )}
                <button onClick={() => alert('Purchase functionality coming soon!')}>Buy More Credits</button>
            </div>

            <hr />

            <form onSubmit={handleUpdateProfile} className="account-form">
                <label>Display Name:</label>
                <input 
                    type="text"
                    value={displayName}
                    onChange={(e) => setDisplayName(e.target.value)}
                    placeholder="Your Name"
                />
                <button type="submit">Update Name</button>
            </form>

            <hr />

            <form onSubmit={(e) => {e.preventDefault(); handleActionRequiringReauth('email')}} className="account-form">
                <label>Email Address:</label>
                <input 
                    type="email"
                    value={newEmail}
                    onChange={(e) => setNewEmail(e.target.value)}
                />
                <button type="submit">Update Email</button>
            </form>
            
            <hr />
            
            <form onSubmit={(e) => {e.preventDefault(); handleActionRequiringReauth('password')}} className="account-form">
                <label>New Password:</label>
                <input 
                    type="password"
                    value={newPassword}
                    onChange={(e) => setNewPassword(e.target.value)}
                    placeholder="New Password (min. 6 characters)"
                />
                <button type="submit">Update Password</button>
            </form>

            <hr />

            <form onSubmit={handleEmailPreferencesUpdate} className="account-form">
                <h3>Email Preferences</h3>
                <p>Choose which types of emails you'd like to receive:</p>
                
                <div className="email-preferences">
                    <label className="checkbox-label">
                        <input 
                            type="checkbox"
                            checked={emailPreferences.feature_updates}
                            onChange={(e) => setEmailPreferences(prev => ({
                                ...prev,
                                feature_updates: e.target.checked
                            }))}
                        />
                        🚀 New Features & Updates
                    </label>
                    
                    <label className="checkbox-label">
                        <input 
                            type="checkbox"
                            checked={emailPreferences.bug_fixes}
                            onChange={(e) => setEmailPreferences(prev => ({
                                ...prev,
                                bug_fixes: e.target.checked
                            }))}
                        />
                        🐛 Bug Fixes & Improvements
                    </label>
                    
                    <label className="checkbox-label">
                        <input 
                            type="checkbox"
                            checked={emailPreferences.pricing_changes}
                            onChange={(e) => setEmailPreferences(prev => ({
                                ...prev,
                                pricing_changes: e.target.checked
                            }))}
                        />
                        💰 Pricing & Plan Changes
                    </label>
                    
                    <label className="checkbox-label">
                        <input 
                            type="checkbox"
                            checked={emailPreferences.usage_tips}
                            onChange={(e) => setEmailPreferences(prev => ({
                                ...prev,
                                usage_tips: e.target.checked
                            }))}
                        />
                        💡 Usage Tips & Best Practices
                    </label>
                </div>
                
                <button type="submit">Update Email Preferences</button>
            </form>
        </div>
    );
};

export default AccountPanel; 