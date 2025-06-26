import React, { useState } from 'react';
import { 
    updateProfile, 
    updateEmail, 
    updatePassword, 
    reauthenticateWithCredential, 
    EmailAuthProvider 
} from 'firebase/auth';

const AccountPanel = ({ auth, onClose }) => {
    const [displayName, setDisplayName] = useState(auth.currentUser?.displayName || '');
    const [newEmail, setNewEmail] = useState(auth.currentUser?.email || '');
    const [newPassword, setNewPassword] = useState('');
    const [currentPassword, setCurrentPassword] = useState('');
    
    const [error, setError] = useState('');
    const [success, setSuccess] = useState('');
    const [needsReauth, setNeedsReauth] = useState(null); // 'email' or 'password'

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
    
    if (needsReauth) {
        return (
            <div className="modal-backdrop">
                <div className="modal-content">
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
            </div>
        );
    }

    return (
        <div className="modal-backdrop" onClick={onClose}>
            <div className="modal-content" onClick={e => e.stopPropagation()}>
                <div className="modal-header">
                    <h2>My Account</h2>
                    <button className="close-modal-btn" onClick={onClose}>&times;</button>
                </div>
                {error && <p className="error">{error}</p>}
                {success && <p className="success">{success}</p>}

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
            </div>
        </div>
    );
};

export default AccountPanel; 