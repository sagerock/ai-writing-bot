import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { API_URL } from '../apiConfig';

const AdminPage = ({ auth }) => {
    const [users, setUsers] = useState([]);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState('');
    
    // Email functionality
    const [emailForm, setEmailForm] = useState({
        subject: '',
        content: '',
        email_type: 'feature_updates',
        preview: false
    });
    const [emailPreview, setEmailPreview] = useState(null);
    const [sendingEmail, setSendingEmail] = useState(false);

    // Debug functionality
    const [debugUserId, setDebugUserId] = useState('');
    const [debugResult, setDebugResult] = useState(null);
    const [debugLoading, setDebugLoading] = useState(false);
    const [creditsSummary, setCreditsSummary] = useState(null);

    const fetchUsers = async () => {
        setLoading(true);
        setError('');
        try {
            const token = await auth.currentUser.getIdToken();
            const response = await fetch(`${API_URL}/admin/users`, {
                headers: { 'Authorization': `Bearer ${token}` }
            });
            if (!response.ok) {
                const errData = await response.json();
                throw new Error(errData.detail || 'Failed to fetch users.');
            }
            const data = await response.json();
            setUsers(data);
        } catch (err) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        if (auth.currentUser) {
            fetchUsers();
        }
    }, [auth.currentUser]);

    const handleUpdateCredits = async (userId, amount) => {
        const amountValue = parseInt(prompt(`Enter the amount of credits to add or remove (e.g., 50 or -10) for ${userId}:`));
        if (isNaN(amountValue)) {
            alert('Invalid number entered.');
            return;
        }

        try {
            const token = await auth.currentUser.getIdToken();
            await fetch(`${API_URL}/admin/users/${userId}/credits`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
                body: JSON.stringify({ amount: amountValue })
            });
            alert('Credits updated successfully!');
            fetchUsers(); // Refresh users list
        } catch (err) {
            alert('Failed to update credits.');
        }
    };

    const handleUpdateRole = async (userId, isAdmin) => {
        if (!window.confirm(`Are you sure you want to ${isAdmin ? 'grant' : 'revoke'} admin rights for ${userId}?`)) {
            return;
        }

        try {
            const token = await auth.currentUser.getIdToken();
            await fetch(`${API_URL}/admin/users/${userId}/role`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
                body: JSON.stringify({ is_admin: isAdmin })
            });
            alert('User role updated successfully!');
            fetchUsers(); // Refresh users list
        } catch (err) {
            alert('Failed to update role.');
        }
    };

    const handleEmailPreview = async () => {
        if (!emailForm.subject || !emailForm.content) {
            alert('Please fill in both subject and content.');
            return;
        }

        try {
            const token = await auth.currentUser.getIdToken();
            const response = await fetch(`${API_URL}/admin/email/preview?email_type=${emailForm.email_type}`, {
                headers: { 'Authorization': `Bearer ${token}` }
            });
            if (!response.ok) {
                throw new Error('Failed to get email preview.');
            }
            const data = await response.json();
            setEmailPreview(data);
        } catch (err) {
            alert('Failed to get email preview: ' + err.message);
        }
    };

    const handleSendEmail = async () => {
        if (!emailForm.subject || !emailForm.content) {
            alert('Please fill in both subject and content.');
            return;
        }

        if (!window.confirm(`Are you sure you want to send this email to ${emailPreview?.recipient_count || 0} users?`)) {
            return;
        }

        setSendingEmail(true);
        try {
            const token = await auth.currentUser.getIdToken();
            const response = await fetch(`${API_URL}/admin/email/send`, {
                method: 'POST',
                headers: { 
                    'Content-Type': 'application/json', 
                    'Authorization': `Bearer ${token}` 
                },
                body: JSON.stringify(emailForm)
            });
            if (!response.ok) {
                throw new Error('Failed to send email.');
            }
            const result = await response.json();
            alert(`Email sent successfully! ${result.message}`);
            setEmailForm({ subject: '', content: '', email_type: 'feature_updates', preview: false });
            setEmailPreview(null);
        } catch (err) {
            alert('Failed to send email: ' + err.message);
        } finally {
            setSendingEmail(false);
        }
    };

    const handleDebugUser = async () => {
        if (!debugUserId.trim()) {
            alert('Please enter a user ID');
            return;
        }

        setDebugLoading(true);
        setDebugResult(null);
        try {
            const token = await auth.currentUser.getIdToken();
            const response = await fetch(`${API_URL}/admin/debug/user/${debugUserId}/credits`, {
                headers: { 'Authorization': `Bearer ${token}` }
            });
            if (!response.ok) {
                throw new Error('Failed to debug user credits');
            }
            const result = await response.json();
            setDebugResult(result);
        } catch (err) {
            alert('Failed to debug user: ' + err.message);
        } finally {
            setDebugLoading(false);
        }
    };

    const handleCreditsSummary = async () => {
        setDebugLoading(true);
        try {
            const token = await auth.currentUser.getIdToken();
            const response = await fetch(`${API_URL}/admin/debug/credits/summary`, {
                headers: { 'Authorization': `Bearer ${token}` }
            });
            if (!response.ok) {
                throw new Error('Failed to get credits summary');
            }
            const result = await response.json();
            setCreditsSummary(result);
        } catch (err) {
            alert('Failed to get credits summary: ' + err.message);
        } finally {
            setDebugLoading(false);
        }
    };

    const handleFixUserCredits = async (userId, credits) => {
        const creditAmount = parseInt(prompt(`Enter the number of credits to set for user ${userId}:`, '100'));
        if (isNaN(creditAmount) || creditAmount < 0) {
            alert('Invalid credit amount');
            return;
        }

        if (!window.confirm(`Are you sure you want to set ${creditAmount} credits for user ${userId}?`)) {
            return;
        }

        try {
            const token = await auth.currentUser.getIdToken();
            const response = await fetch(`${API_URL}/admin/debug/user/${userId}/fix-credits?credit_amount=${creditAmount}`, {
                method: 'POST',
                headers: { 'Authorization': `Bearer ${token}` }
            });
            if (!response.ok) {
                throw new Error('Failed to fix user credits');
            }
            const result = await response.json();
            alert(`Credits fixed successfully! User now has ${result.new_credits} credits.`);
            fetchUsers(); // Refresh users list
        } catch (err) {
            alert('Failed to fix credits: ' + err.message);
        }
    };

    const debugSpecificUser = async (userId) => {
        setDebugUserId(userId);
        setDebugLoading(true);
        setDebugResult(null);
        try {
            const token = await auth.currentUser.getIdToken();
            const response = await fetch(`${API_URL}/admin/debug/user/${userId}/credits`, {
                headers: { 'Authorization': `Bearer ${token}` }
            });
            if (!response.ok) {
                throw new Error('Failed to debug user credits');
            }
            const result = await response.json();
            setDebugResult(result);
        } catch (err) {
            alert('Failed to debug user: ' + err.message);
        } finally {
            setDebugLoading(false);
        }
    };

    return (
        <div className="admin-page">
            <nav className="account-nav">
                <Link to="/">&larr; Back to Chat</Link>
            </nav>
            <div className="admin-panel">
                <h1>Admin Panel</h1>
                {loading && <p>Loading users...</p>}
                {error && <p className="error">{error}</p>}
                <table className="users-table">
                    <thead>
                        <tr>
                            <th>UID</th>
                            <th>Email</th>
                            <th>Display Name</th>
                            <th>Credits Left</th>
                            <th>Credits Used</th>
                            <th>Is Admin?</th>
                            <th>Actions</th>
                        </tr>
                    </thead>
                    <tbody>
                        {users.map(user => (
                            <tr key={user.uid}>
                                <td>{user.uid}</td>
                                <td>{user.email}</td>
                                <td>{user.displayName}</td>
                                <td>{user.credits}</td>
                                <td>{user.credits_used || 0}</td>
                                <td>{user.isAdmin ? 'Yes' : 'No'}</td>
                                <td>
                                    <button onClick={() => handleUpdateCredits(user.uid)}>Update Credits</button>
                                    <button onClick={() => debugSpecificUser(user.uid)}>Debug</button>
                                    {!user.isAdmin ? (
                                        <button onClick={() => handleUpdateRole(user.uid, true)}>Make Admin</button>
                                    ) : (
                                        <button onClick={() => handleUpdateRole(user.uid, false)}>Revoke Admin</button>
                                    )}
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>

            <div className="admin-panel">
                <h2>Send Email to Users</h2>
                <div className="email-form">
                    <div className="form-group">
                        <label>Email Type:</label>
                        <select 
                            value={emailForm.email_type} 
                            onChange={(e) => setEmailForm(prev => ({ ...prev, email_type: e.target.value }))}
                        >
                            <option value="feature_updates">🚀 New Features & Updates</option>
                            <option value="bug_fixes">🐛 Bug Fixes & Improvements</option>
                            <option value="pricing_changes">💰 Pricing & Plan Changes</option>
                            <option value="usage_tips">💡 Usage Tips & Best Practices</option>
                            <option value="all">📢 All Users (Announcement)</option>
                        </select>
                    </div>

                    <div className="form-group">
                        <label>Subject:</label>
                        <input 
                            type="text" 
                            value={emailForm.subject}
                            onChange={(e) => setEmailForm(prev => ({ ...prev, subject: e.target.value }))}
                            placeholder="Email subject..."
                        />
                    </div>

                    <div className="form-group">
                        <label>Content:</label>
                        <textarea 
                            value={emailForm.content}
                            onChange={(e) => setEmailForm(prev => ({ ...prev, content: e.target.value }))}
                            placeholder="Email content (supports HTML)..."
                            rows="8"
                        />
                    </div>

                    <div className="email-actions">
                        <button onClick={handleEmailPreview} disabled={sendingEmail}>
                            Preview Recipients
                        </button>
                        <button 
                            onClick={handleSendEmail} 
                            disabled={sendingEmail || !emailPreview}
                            className="send-button"
                        >
                            {sendingEmail ? 'Sending...' : 'Send Email'}
                        </button>
                    </div>

                    {emailPreview && (
                        <div className="email-preview">
                            <h3>Email Preview</h3>
                            <p><strong>Type:</strong> {emailPreview.email_type}</p>
                            <p><strong>Recipients:</strong> {emailPreview.recipient_count} users</p>
                            {emailPreview.recipients && emailPreview.recipients.length > 0 && (
                                <div>
                                    <p><strong>Sample Recipients:</strong></p>
                                    <ul>
                                        {emailPreview.recipients.slice(0, 5).map((user, index) => (
                                            <li key={index}>{user.email} ({user.display_name})</li>
                                        ))}
                                        {emailPreview.recipients.length > 5 && (
                                            <li>... and {emailPreview.recipients.length - 5} more</li>
                                        )}
                                    </ul>
                                </div>
                            )}
                        </div>
                    )}
                </div>
            </div>

            <div className="admin-panel">
                <h2>🔧 Credit System Debug Tools</h2>
                
                <div className="debug-section">
                    <div className="form-group">
                        <label>Debug Specific User:</label>
                        <div style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
                            <input 
                                type="text" 
                                value={debugUserId}
                                onChange={(e) => setDebugUserId(e.target.value)}
                                placeholder="Enter User ID (UID)..."
                                style={{ flex: 1 }}
                            />
                            <button onClick={handleDebugUser} disabled={debugLoading}>
                                {debugLoading ? 'Debugging...' : 'Debug User'}
                            </button>
                        </div>
                    </div>

                    <div className="form-group">
                        <button onClick={handleCreditsSummary} disabled={debugLoading}>
                            {debugLoading ? 'Loading...' : 'Get Credits Summary (All Users)'}
                        </button>
                    </div>

                    {debugResult && (
                        <div className="debug-result">
                            <h3>Debug Result for User: {debugResult.user_id}</h3>
                            <div className="debug-info">
                                <div className="debug-section-item">
                                    <h4>Firebase Auth Status:</h4>
                                    <p>Exists: {debugResult.firebase_auth.exists ? '✅ Yes' : '❌ No'}</p>
                                    {debugResult.firebase_auth.data && (
                                        <div>
                                            <p>Email: {debugResult.firebase_auth.data.email}</p>
                                            <p>Verified: {debugResult.firebase_auth.data.email_verified ? 'Yes' : 'No'}</p>
                                            <p>Disabled: {debugResult.firebase_auth.data.disabled ? 'Yes' : 'No'}</p>
                                        </div>
                                    )}
                                </div>

                                <div className="debug-section-item">
                                    <h4>Firestore Document:</h4>
                                    <p>Exists: {debugResult.firestore.document_exists ? '✅ Yes' : '❌ No'}</p>
                                    {debugResult.firestore.raw_data && (
                                        <pre>{JSON.stringify(debugResult.firestore.raw_data, null, 2)}</pre>
                                    )}
                                </div>

                                <div className="debug-section-item">
                                    <h4>Credit Check Simulation:</h4>
                                    <p>Status: {debugResult.credit_simulation.status}</p>
                                    {debugResult.credit_simulation.current_credits !== undefined && (
                                        <p>Current Credits: {debugResult.credit_simulation.current_credits}</p>
                                    )}
                                    <p>Would Pass Check: {debugResult.credit_simulation.would_pass_check ? '✅ Yes' : '❌ No'}</p>
                                </div>

                                <div className="debug-section-item diagnosis">
                                    <h4>Diagnosis:</h4>
                                    <p><strong>Issue:</strong> {debugResult.diagnosis.likely_issue}</p>
                                    <div>
                                        <strong>Recommendations:</strong>
                                        <ul>
                                            {debugResult.diagnosis.recommendations.map((rec, index) => (
                                                <li key={index}>{rec}</li>
                                            ))}
                                        </ul>
                                    </div>
                                    {debugResult.credit_simulation.current_credits <= 0 && (
                                        <button 
                                            onClick={() => handleFixUserCredits(debugResult.user_id)}
                                            className="fix-credits-btn"
                                            style={{ marginTop: '10px', backgroundColor: '#28a745', color: 'white' }}
                                        >
                                            🔧 Fix Credits
                                        </button>
                                    )}
                                </div>
                            </div>
                        </div>
                    )}

                    {creditsSummary && (
                        <div className="credits-summary">
                            <h3>Credits Summary (All Users)</h3>
                            <div className="summary-stats">
                                <div className="stat-item">
                                    <span>Total Users Checked:</span>
                                    <span>{creditsSummary.total_users_checked}</span>
                                </div>
                                <div className="stat-item">
                                    <span>Users With Credits:</span>
                                    <span className="stat-good">{creditsSummary.users_with_credits}</span>
                                </div>
                                <div className="stat-item">
                                    <span>Users Out of Credits:</span>
                                    <span className="stat-warning">{creditsSummary.users_out_of_credits}</span>
                                </div>
                                <div className="stat-item">
                                    <span>Users Without Data:</span>
                                    <span className="stat-info">{creditsSummary.users_no_firestore_data}</span>
                                </div>
                                <div className="stat-item">
                                    <span>Users With Errors:</span>
                                    <span className="stat-error">{creditsSummary.users_with_errors}</span>
                                </div>
                            </div>

                            {creditsSummary.sample_issues.length > 0 && (
                                <div className="sample-issues">
                                    <h4>Sample Issues Found:</h4>
                                    {creditsSummary.sample_issues.map((issue, index) => (
                                        <div key={index} className="issue-item">
                                            <span>{issue.email} ({issue.user_id.substring(0, 8)}...)</span>
                                            <span>Issue: {issue.issue}</span>
                                            <span>Credits: {issue.credits}</span>
                                            <button 
                                                onClick={() => handleFixUserCredits(issue.user_id)}
                                                className="fix-credits-btn-small"
                                            >
                                                Fix
                                            </button>
                                        </div>
                                    ))}
                                </div>
                            )}
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
};

export default AdminPage; 