import React, { useState, useEffect, useRef } from 'react';
import { Link } from 'react-router-dom';
import { API_URL } from '../apiConfig';

const AdminUsersPage = ({ auth }) => {
    const [users, setUsers] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');

    // Search and filter state
    const [searchQuery, setSearchQuery] = useState('');
    const [adminFilter, setAdminFilter] = useState('all'); // 'all' | 'admin' | 'user'

    // Inline editing state
    const [editingCell, setEditingCell] = useState(null); // { uid, field }
    const [editValue, setEditValue] = useState('');
    const [saving, setSaving] = useState(false);
    const inputRef = useRef(null);

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

    // Focus input when editing starts
    useEffect(() => {
        if (editingCell && inputRef.current) {
            inputRef.current.focus();
            inputRef.current.select();
        }
    }, [editingCell]);

    // Filter users based on search and admin filter
    const filteredUsers = users.filter(user => {
        const matchesSearch = searchQuery === '' ||
            user.email?.toLowerCase().includes(searchQuery.toLowerCase()) ||
            user.displayName?.toLowerCase().includes(searchQuery.toLowerCase()) ||
            user.uid.toLowerCase().includes(searchQuery.toLowerCase());

        const matchesFilter = adminFilter === 'all' ||
            (adminFilter === 'admin' && user.isAdmin) ||
            (adminFilter === 'user' && !user.isAdmin);

        return matchesSearch && matchesFilter;
    });

    const startEditing = (uid, field, currentValue) => {
        setEditingCell({ uid, field });
        setEditValue(currentValue?.toString() || '');
    };

    const cancelEditing = () => {
        setEditingCell(null);
        setEditValue('');
    };

    const saveEdit = async () => {
        if (!editingCell) return;

        const { uid, field } = editingCell;
        const user = users.find(u => u.uid === uid);

        // Check if value actually changed
        const originalValue = user[field];
        if (editValue === originalValue?.toString()) {
            cancelEditing();
            return;
        }

        setSaving(true);
        try {
            const token = await auth.currentUser.getIdToken();

            if (field === 'credits') {
                const newCredits = parseInt(editValue);
                if (isNaN(newCredits)) {
                    alert('Invalid number');
                    setSaving(false);
                    return;
                }
                // Calculate the difference to add/subtract
                const difference = newCredits - (user.credits || 0);
                await fetch(`${API_URL}/admin/users/${uid}/credits`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Authorization': `Bearer ${token}`
                    },
                    body: JSON.stringify({ amount: difference })
                });
            } else if (field === 'displayName') {
                await fetch(`${API_URL}/admin/users/${uid}`, {
                    method: 'PUT',
                    headers: {
                        'Content-Type': 'application/json',
                        'Authorization': `Bearer ${token}`
                    },
                    body: JSON.stringify({ display_name: editValue })
                });
            }

            // Update local state immediately for responsiveness
            setUsers(prev => prev.map(u =>
                u.uid === uid ? { ...u, [field]: field === 'credits' ? parseInt(editValue) : editValue } : u
            ));
            cancelEditing();
        } catch (err) {
            alert('Failed to save: ' + err.message);
        } finally {
            setSaving(false);
        }
    };

    const toggleAdmin = async (uid, currentIsAdmin) => {
        if (!window.confirm(`Are you sure you want to ${currentIsAdmin ? 'revoke' : 'grant'} admin rights?`)) {
            return;
        }

        setSaving(true);
        try {
            const token = await auth.currentUser.getIdToken();
            await fetch(`${API_URL}/admin/users/${uid}/role`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${token}`
                },
                body: JSON.stringify({ is_admin: !currentIsAdmin })
            });

            // Update local state
            setUsers(prev => prev.map(u =>
                u.uid === uid ? { ...u, isAdmin: !currentIsAdmin } : u
            ));
        } catch (err) {
            alert('Failed to update role: ' + err.message);
        } finally {
            setSaving(false);
        }
    };

    const handleKeyDown = (e) => {
        if (e.key === 'Enter') {
            saveEdit();
        } else if (e.key === 'Escape') {
            cancelEditing();
        }
    };

    const copyToClipboard = (text) => {
        navigator.clipboard.writeText(text);
    };

    return (
        <div className="admin-page">
            <nav className="account-nav">
                <Link to="/admin">&larr; Back to Admin</Link>
            </nav>

            <div className="admin-panel">
                <h1>User Management</h1>

                {/* Search and Filters */}
                <div className="users-search-filters">
                    <input
                        type="text"
                        className="users-search-input"
                        placeholder="Search by email, name, or UID..."
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                    />
                    <div className="users-filter-buttons">
                        <button
                            className={`filter-btn ${adminFilter === 'all' ? 'active' : ''}`}
                            onClick={() => setAdminFilter('all')}
                        >
                            All ({users.length})
                        </button>
                        <button
                            className={`filter-btn ${adminFilter === 'admin' ? 'active' : ''}`}
                            onClick={() => setAdminFilter('admin')}
                        >
                            Admins ({users.filter(u => u.isAdmin).length})
                        </button>
                        <button
                            className={`filter-btn ${adminFilter === 'user' ? 'active' : ''}`}
                            onClick={() => setAdminFilter('user')}
                        >
                            Users ({users.filter(u => !u.isAdmin).length})
                        </button>
                    </div>
                </div>

                <p className="users-count">
                    Showing {filteredUsers.length} of {users.length} users
                </p>

                {loading && <p>Loading users...</p>}
                {error && <p className="error">{error}</p>}

                {!loading && !error && (
                    <table className="users-table">
                        <thead>
                            <tr>
                                <th>UID</th>
                                <th>Email</th>
                                <th>Display Name</th>
                                <th>Credits</th>
                                <th>Used</th>
                                <th>Admin</th>
                            </tr>
                        </thead>
                        <tbody>
                            {filteredUsers.map(user => (
                                <tr key={user.uid}>
                                    {/* UID - Read only with copy */}
                                    <td className="uid-cell">
                                        <span className="uid-text" title={user.uid}>
                                            {user.uid.substring(0, 8)}...
                                        </span>
                                        <button
                                            className="copy-btn"
                                            onClick={() => copyToClipboard(user.uid)}
                                            title="Copy full UID"
                                        >
                                            📋
                                        </button>
                                    </td>

                                    {/* Email - Read only */}
                                    <td>{user.email}</td>

                                    {/* Display Name - Editable */}
                                    <td
                                        className={`editable-cell ${editingCell?.uid === user.uid && editingCell?.field === 'displayName' ? 'editing' : ''}`}
                                        onClick={() => !editingCell && startEditing(user.uid, 'displayName', user.displayName)}
                                    >
                                        {editingCell?.uid === user.uid && editingCell?.field === 'displayName' ? (
                                            <input
                                                ref={inputRef}
                                                type="text"
                                                value={editValue}
                                                onChange={(e) => setEditValue(e.target.value)}
                                                onKeyDown={handleKeyDown}
                                                onBlur={saveEdit}
                                                disabled={saving}
                                            />
                                        ) : (
                                            <span className="editable-value">
                                                {user.displayName || <em className="empty-value">-</em>}
                                            </span>
                                        )}
                                    </td>

                                    {/* Credits - Editable */}
                                    <td
                                        className={`editable-cell ${editingCell?.uid === user.uid && editingCell?.field === 'credits' ? 'editing' : ''}`}
                                        onClick={() => !editingCell && startEditing(user.uid, 'credits', user.credits)}
                                    >
                                        {editingCell?.uid === user.uid && editingCell?.field === 'credits' ? (
                                            <input
                                                ref={inputRef}
                                                type="number"
                                                value={editValue}
                                                onChange={(e) => setEditValue(e.target.value)}
                                                onKeyDown={handleKeyDown}
                                                onBlur={saveEdit}
                                                disabled={saving}
                                            />
                                        ) : (
                                            <span className="editable-value">{user.credits}</span>
                                        )}
                                    </td>

                                    {/* Credits Used - Read only */}
                                    <td>{user.credits_used || 0}</td>

                                    {/* Admin Toggle */}
                                    <td className="admin-toggle-cell">
                                        <label className="toggle-switch">
                                            <input
                                                type="checkbox"
                                                checked={user.isAdmin}
                                                onChange={() => toggleAdmin(user.uid, user.isAdmin)}
                                                disabled={saving}
                                            />
                                            <span className="toggle-slider"></span>
                                        </label>
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                )}

                {!loading && !error && filteredUsers.length === 0 && (
                    <p className="no-results">No users match your search.</p>
                )}
            </div>
        </div>
    );
};

export default AdminUsersPage;
