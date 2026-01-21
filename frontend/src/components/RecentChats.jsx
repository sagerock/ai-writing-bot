import React, { useState, useEffect } from 'react';
import { API_URL } from '../apiConfig';

const RecentChats = ({ auth, onLoadChat, onLoadDocument }) => {
    const [chats, setChats] = useState([]);
    const [documents, setDocuments] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');
    const [activeTab, setActiveTab] = useState('chats');

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

    const fetchDocuments = async () => {
        if (!auth.currentUser) return;

        try {
            const token = await auth.currentUser.getIdToken();
            const response = await fetch(`${API_URL}/documents`, {
                headers: { 'Authorization': `Bearer ${token}` }
            });

            if (!response.ok) {
                throw new Error('Failed to load documents');
            }

            const projectData = await response.json();

            // Flatten all documents from all projects into a single list
            const allDocs = [];
            Object.values(projectData).forEach(projectDocs => {
                allDocs.push(...projectDocs);
            });

            // Sort by date, newest first
            allDocs.sort((a, b) => {
                const dateA = a.uploadedAt ? new Date(a.uploadedAt) : new Date(0);
                const dateB = b.uploadedAt ? new Date(b.uploadedAt) : new Date(0);
                return dateB - dateA;
            });

            setDocuments(allDocs);
        } catch (err) {
            console.error('Error fetching documents:', err);
        }
    };

    const handleDeleteDocument = async (filename, e) => {
        e.stopPropagation();

        if (!window.confirm('Delete this document?')) {
            return;
        }

        try {
            const token = await auth.currentUser.getIdToken();
            const response = await fetch(`${API_URL}/document/${encodeURIComponent(filename)}`, {
                method: 'DELETE',
                headers: { 'Authorization': `Bearer ${token}` }
            });

            if (!response.ok) {
                throw new Error('Failed to delete');
            }

            // Remove from local state
            setDocuments(prev => prev.filter(doc => doc.filename !== filename));
        } catch (err) {
            alert('Failed to delete document');
        }
    };

    const handleLoadDocument = async (doc) => {
        try {
            const token = await auth.currentUser.getIdToken();
            const response = await fetch(`${API_URL}/document/${encodeURIComponent(doc.filename)}`, {
                headers: { 'Authorization': `Bearer ${token}` }
            });

            if (!response.ok) {
                throw new Error('Failed to load document');
            }

            const data = await response.json();

            if (onLoadDocument) {
                onLoadDocument({
                    role: 'context',
                    content: data.content,
                    display_text: `Loaded document: ${doc.filename}`
                });
            }
        } catch (err) {
            alert('Failed to load document');
        }
    };

    const handleDownloadDocument = async (filename, e) => {
        e.stopPropagation();

        try {
            const token = await auth.currentUser.getIdToken();
            const response = await fetch(`${API_URL}/document/${encodeURIComponent(filename)}/download`, {
                headers: { 'Authorization': `Bearer ${token}` }
            });

            if (!response.ok) {
                throw new Error('Failed to get download link');
            }

            const data = await response.json();

            // Open the download URL in a new tab
            window.open(data.download_url, '_blank');
        } catch (err) {
            alert('Failed to download document');
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

    const formatFileSize = (bytes) => {
        if (!bytes) return '';
        if (bytes < 1024) return `${bytes} B`;
        if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
        return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
    };

    const refreshAll = () => {
        fetchChats();
        fetchDocuments();
    };

    useEffect(() => {
        fetchChats();
        fetchDocuments();
    }, [auth.currentUser]);

    return (
        <div className="recent-chats">
            <div className="recent-chats-header">
                <div className="sidebar-tabs">
                    <button
                        className={`sidebar-tab ${activeTab === 'chats' ? 'active' : ''}`}
                        onClick={() => setActiveTab('chats')}
                    >
                        Chats
                    </button>
                    <button
                        className={`sidebar-tab ${activeTab === 'documents' ? 'active' : ''}`}
                        onClick={() => setActiveTab('documents')}
                    >
                        Files
                    </button>
                </div>
                <button onClick={refreshAll} className="refresh-btn" title="Refresh">
                    {loading ? '...' : '↻'}
                </button>
            </div>

            {error && <p className="error-text">{error}</p>}

            {activeTab === 'chats' && (
                <>
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
                </>
            )}

            {activeTab === 'documents' && (
                <>
                    {documents.length === 0 && (
                        <p className="empty-text">No documents uploaded yet</p>
                    )}

                    <div className="chat-list">
                        {documents.map(doc => (
                            <div
                                key={doc.filename}
                                className="chat-item document-item"
                                onClick={() => handleLoadDocument(doc)}
                            >
                                <div className="chat-item-content">
                                    <div className="chat-title">
                                        <span className="file-icon">📄</span>
                                        {doc.filename}
                                    </div>
                                    <div className="chat-meta">
                                        <span className="chat-date">{formatDate(doc.uploadedAt)}</span>
                                        {doc.size && (
                                            <span className="chat-count">{formatFileSize(doc.size)}</span>
                                        )}
                                    </div>
                                </div>
                                <div className="document-actions">
                                    <button
                                        className="download-btn"
                                        onClick={(e) => handleDownloadDocument(doc.filename, e)}
                                        title="Download original file"
                                    >
                                        ⬇
                                    </button>
                                    <button
                                        className="delete-chat-btn"
                                        onClick={(e) => handleDeleteDocument(doc.filename, e)}
                                        title="Delete"
                                    >
                                        ×
                                    </button>
                                </div>
                            </div>
                        ))}
                    </div>
                </>
            )}
        </div>
    );
};

export default RecentChats;
