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
        </div>
    );
};

export default AdminPage; 