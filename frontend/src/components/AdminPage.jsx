import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';

const AdminPage = ({ auth }) => {
    const [users, setUsers] = useState([]);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState('');

    const fetchUsers = async () => {
        setLoading(true);
        setError('');
        try {
            const token = await auth.currentUser.getIdToken();
            const response = await fetch('http://127.0.0.1:8000/admin/users', {
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
            await fetch(`http://127.0.0.1:8000/admin/users/${userId}/credits`, {
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
            await fetch(`http://127.0.0.1:8000/admin/users/${userId}/role`, {
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
                            <th>Credits</th>
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
        </div>
    );
};

export default AdminPage; 