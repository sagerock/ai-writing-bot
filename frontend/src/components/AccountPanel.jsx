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
    const [documents, setDocuments] = useState([]);
    const [documentsLoading, setDocumentsLoading] = useState(true);
    const [deletingDoc, setDeletingDoc] = useState(null);
    const [emailPreferences, setEmailPreferences] = useState({
        feature_updates: true,
        bug_fixes: true,
        pricing_changes: true,
        usage_tips: true
    });
    const [chatSettings, setChatSettings] = useState({
        simplified_mode: true,
        default_model: 'auto',
        default_temperature: 0.7,
        always_ask_mode: false
    });
    const [error, setError] = useState('');
    const [success, setSuccess] = useState('');
    const [needsReauth, setNeedsReauth] = useState(null); // 'email' or 'password'

    const MODEL_OPTIONS = [
        { value: 'auto', label: 'Auto (Smart Routing)' },
        { value: 'gpt-5-nano-2025-08-07', label: 'GPT-5 Nano (Fastest)' },
        { value: 'gpt-5-mini-2025-08-07', label: 'GPT-5 Mini (Balanced)' },
        { value: 'gpt-5-2025-08-07', label: 'GPT-5 (Advanced)' },
        { value: 'gpt-5-pro', label: 'GPT-5 Pro (Most Capable)' },
        { value: 'claude-sonnet-4-5-20250929', label: 'Claude Sonnet 4.5' },
        { value: 'claude-opus-4-5-20251101', label: 'Claude Opus 4.5' },
        { value: 'gemini-3-pro-preview', label: 'Gemini 3 Pro' },
        { value: 'gemini-2.5-pro', label: 'Gemini 2.5 Pro' },
        { value: 'gemini-2.5-flash', label: 'Gemini 2.5 Flash' },
        { value: 'gemini-2.0-flash', label: 'Gemini 2.0 Flash' },
    ];

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

        const fetchChatSettings = async () => {
            if (!auth.currentUser) return;
            try {
                const token = await auth.currentUser.getIdToken();
                const response = await fetch(`${API_URL}/user/chat-settings`, {
                    headers: {
                        'Authorization': `Bearer ${token}`
                    }
                });
                if (response.ok) {
                    const data = await response.json();
                    setChatSettings(data);
                }
            } catch (err) {
                console.error('Could not load chat settings:', err);
            }
        };

        const fetchDocuments = async () => {
            if (!auth.currentUser) return;
            setDocumentsLoading(true);
            try {
                const token = await auth.currentUser.getIdToken();
                const response = await fetch(`${API_URL}/documents/indexed`, {
                    headers: {
                        'Authorization': `Bearer ${token}`
                    }
                });
                if (response.ok) {
                    const data = await response.json();
                    setDocuments(data.documents || []);
                }
            } catch (err) {
                console.error('Could not load documents:', err);
            } finally {
                setDocumentsLoading(false);
            }
        };

        fetchCredits();
        fetchEmailPreferences();
        fetchChatSettings();
        fetchDocuments();
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

    const handleChatSettingsUpdate = async (e) => {
        e.preventDefault();
        setError('');
        setSuccess('');
        try {
            const token = await auth.currentUser.getIdToken();
            const response = await fetch(`${API_URL}/user/chat-settings`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${token}`
                },
                body: JSON.stringify(chatSettings)
            });
            if (!response.ok) {
                throw new Error('Failed to update chat settings.');
            }
            setSuccess('Chat settings updated! Refresh the page to see changes.');
        } catch (err) {
            setError('Failed to update chat settings.');
            console.error(err);
        }
    };

    const handleDeleteDocument = async (filename) => {
        if (!window.confirm(`Are you sure you want to delete "${filename}"? This will remove it from your AI's knowledge base.`)) {
            return;
        }

        setDeletingDoc(filename);
        setError('');
        setSuccess('');

        try {
            const token = await auth.currentUser.getIdToken();
            const response = await fetch(`${API_URL}/document/${encodeURIComponent(filename)}`, {
                method: 'DELETE',
                headers: {
                    'Authorization': `Bearer ${token}`
                }
            });

            if (!response.ok) {
                const data = await response.json();
                throw new Error(data.detail || 'Failed to delete document.');
            }

            setDocuments(prev => prev.filter(doc => doc.filename !== filename));
            setSuccess(`Document "${filename}" deleted successfully.`);
        } catch (err) {
            setError(`Failed to delete document: ${err.message}`);
            console.error(err);
        } finally {
            setDeletingDoc(null);
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

            <div className="account-documents">
                <h3>Your Documents</h3>
                <p>These documents are indexed in your AI's knowledge base for reference during chats.</p>

                {documentsLoading ? (
                    <p className="documents-loading">Loading documents...</p>
                ) : documents.length === 0 ? (
                    <p className="documents-empty">No documents uploaded yet. Upload documents in the chat to add them to your knowledge base.</p>
                ) : (
                    <div className="documents-list">
                        {documents.map((doc, index) => (
                            <div key={index} className="document-item">
                                <div className="document-info">
                                    <span className="document-name">{doc.filename}</span>
                                    <span className="document-meta">
                                        {doc.chunk_count} chunks | {doc.project_name}
                                    </span>
                                </div>
                                <button
                                    className="document-delete-btn"
                                    onClick={() => handleDeleteDocument(doc.filename)}
                                    disabled={deletingDoc === doc.filename}
                                >
                                    {deletingDoc === doc.filename ? 'Deleting...' : 'Delete'}
                                </button>
                            </div>
                        ))}
                    </div>
                )}
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

            <hr />

            <form onSubmit={handleChatSettingsUpdate} className="account-form chat-settings-section">
                <h3>Chat Settings</h3>
                <p>Customize your AI chat experience:</p>

                <div className="chat-settings">
                    <label className="toggle-label">
                        <span className="toggle-text">
                            <strong>Simplified Mode</strong>
                            <small>Hide model selection and project panels for a cleaner experience</small>
                        </span>
                        <div className="toggle-switch">
                            <input
                                type="checkbox"
                                checked={chatSettings.simplified_mode}
                                onChange={(e) => setChatSettings(prev => ({
                                    ...prev,
                                    simplified_mode: e.target.checked
                                }))}
                            />
                            <span className="toggle-slider"></span>
                        </div>
                    </label>

                    <label className="select-label">
                        <span>Default AI Model</span>
                        <select
                            value={chatSettings.default_model}
                            onChange={(e) => setChatSettings(prev => ({
                                ...prev,
                                default_model: e.target.value
                            }))}
                        >
                            {MODEL_OPTIONS.map(opt => (
                                <option key={opt.value} value={opt.value}>{opt.label}</option>
                            ))}
                        </select>
                    </label>

                    <label className="slider-label">
                        <span>Default Creativity Level</span>
                        <div className="slider-container">
                            <input
                                type="range"
                                min="0"
                                max="1.5"
                                step="0.1"
                                value={chatSettings.default_temperature}
                                onChange={(e) => setChatSettings(prev => ({
                                    ...prev,
                                    default_temperature: parseFloat(e.target.value)
                                }))}
                            />
                            <span className="slider-value">
                                {chatSettings.default_temperature <= 0.3 ? 'Focused' :
                                 chatSettings.default_temperature <= 0.7 ? 'Balanced' :
                                 chatSettings.default_temperature <= 1.2 ? 'Creative' : 'Wild'}
                                ({chatSettings.default_temperature})
                            </span>
                        </div>
                    </label>
                </div>

                <button type="submit">Update Chat Settings</button>
            </form>
        </div>
    );
};

export default AccountPanel; 