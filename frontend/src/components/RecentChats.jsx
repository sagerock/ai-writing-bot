import React, { useState, useEffect } from 'react';
import { API_URL } from '../apiConfig';

const RecentChats = ({ auth, onLoadChat }) => {
    const [chats, setChats] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');

    const fetchChats = async () => {
        if (!auth.currentUser) return;

        setLoading(true);
        setError('');

        try {
            const token = await auth.currentUser.getIdToken();
            const response = await fetch(`${API_URL}/archives`, {
                headers: { 'Authorization': `Bearer ${token}` }
            });

            if (!response.ok) {
                throw new Error('Failed to load chats');
            }

            const projectData = await response.json();

            // Flatten all chats from all projects into a single list
            const allChats = [];
            Object.values(projectData).forEach(projectChats => {
                allChats.push(...projectChats);
            });

            // Sort by date, newest first
            allChats.sort((a, b) => {
                const dateA = a.archivedAt ? new Date(a.archivedAt) : new Date(0);
                const dateB = b.archivedAt ? new Date(b.archivedAt) : new Date(0);
                return dateB - dateA;
            });

            setChats(allChats);
        } catch (err) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    };

    const handleDelete = async (chatId, e) => {
        e.stopPropagation();

        if (!window.confirm('Delete this conversation?')) {
            return;
        }

        try {
            const token = await auth.currentUser.getIdToken();
            const response = await fetch(`${API_URL}/archive/${chatId}`, {
                method: 'DELETE',
                headers: { 'Authorization': `Bearer ${token}` }
            });

            if (!response.ok) {
                throw new Error('Failed to delete');
            }

            // Remove from local state
            setChats(prev => prev.filter(chat => chat.id !== chatId));
        } catch (err) {
            alert('Failed to delete conversation');
        }
    };

    const formatDate = (dateString) => {
        if (!dateString) return '';

        const date = new Date(dateString);
        const now = new Date();
        const diffMs = now - date;
        const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

        if (diffDays === 0) {
            return 'Today';
        } else if (diffDays === 1) {
            return 'Yesterday';
        } else if (diffDays < 7) {
            return `${diffDays} days ago`;
        } else {
            return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
        }
    };

    useEffect(() => {
        fetchChats();
    }, [auth.currentUser]);

    return (
        <div className="recent-chats">
            <div className="recent-chats-header">
                <h3>Recent Chats</h3>
                <button onClick={fetchChats} className="refresh-btn" title="Refresh">
                    {loading ? '...' : '↻'}
                </button>
            </div>

            {error && <p className="error-text">{error}</p>}

            {!loading && chats.length === 0 && (
                <p className="empty-text">No previous conversations yet</p>
            )}

            <div className="chat-list">
                {chats.map(chat => (
                    <div
                        key={chat.id}
                        className="chat-item"
                        onClick={() => onLoadChat(chat.id)}
                    >
                        <div className="chat-item-content">
                            <div className="chat-title">{chat.title}</div>
                            <div className="chat-preview">{chat.preview}</div>
                            <div className="chat-meta">
                                <span className="chat-date">{formatDate(chat.archivedAt)}</span>
                                {chat.messageCount && (
                                    <span className="chat-count">{chat.messageCount} messages</span>
                                )}
                            </div>
                        </div>
                        <button
                            className="delete-chat-btn"
                            onClick={(e) => handleDelete(chat.id, e)}
                            title="Delete"
                        >
                            ×
                        </button>
                    </div>
                ))}
            </div>
        </div>
    );
};

export default RecentChats;
