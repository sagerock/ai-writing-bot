import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { API_URL } from '../apiConfig';

const MemoriesPage = ({ auth }) => {
    const [memories, setMemories] = useState([]);
    const [loading, setLoading] = useState(true);
    const [deletingMemory, setDeletingMemory] = useState(null);
    const [error, setError] = useState('');
    const [success, setSuccess] = useState('');

    useEffect(() => {
        const fetchMemories = async () => {
            if (!auth.currentUser) return;
            setLoading(true);
            try {
                const token = await auth.currentUser.getIdToken();
                const response = await fetch(`${API_URL}/user/memories`, {
                    headers: {
                        'Authorization': `Bearer ${token}`
                    }
                });
                if (response.ok) {
                    const data = await response.json();
                    setMemories(data.memories || []);
                }
            } catch (err) {
                console.error('Could not load memories:', err);
                setError('Failed to load memories.');
            } finally {
                setLoading(false);
            }
        };

        fetchMemories();
    }, [auth.currentUser]);

    const handleDeleteMemory = async (memoryId) => {
        if (!window.confirm('Are you sure you want to delete this memory? The AI will no longer remember this information.')) {
            return;
        }

        setDeletingMemory(memoryId);
        setError('');
        setSuccess('');

        try {
            const token = await auth.currentUser.getIdToken();
            const response = await fetch(`${API_URL}/user/memories/${encodeURIComponent(memoryId)}`, {
                method: 'DELETE',
                headers: {
                    'Authorization': `Bearer ${token}`
                }
            });

            if (!response.ok) {
                const data = await response.json();
                throw new Error(data.error || 'Failed to delete memory.');
            }

            setMemories(prev => prev.filter(m => m.id !== memoryId));
            setSuccess('Memory deleted successfully.');
        } catch (err) {
            setError(`Failed to delete memory: ${err.message}`);
            console.error(err);
        } finally {
            setDeletingMemory(null);
        }
    };

    const handleDeleteAllMemories = async () => {
        if (!window.confirm('Are you sure you want to delete ALL memories? This cannot be undone and the AI will forget everything about you.')) {
            return;
        }

        setError('');
        setSuccess('');

        try {
            const token = await auth.currentUser.getIdToken();
            const response = await fetch(`${API_URL}/user/memories`, {
                method: 'DELETE',
                headers: {
                    'Authorization': `Bearer ${token}`
                }
            });

            if (!response.ok) {
                const data = await response.json();
                throw new Error(data.error || 'Failed to delete memories.');
            }

            setMemories([]);
            setSuccess('All memories deleted successfully.');
        } catch (err) {
            setError(`Failed to delete memories: ${err.message}`);
            console.error(err);
        }
    };

    return (
        <div className="memories-page">
            <div className="memories-page-header">
                <Link to="/account" className="back-link">&larr; Back to Account</Link>
                <h1>AI Memories</h1>
                <p>These are things the AI has learned about you from your conversations. This information helps personalize your experience.</p>
            </div>

            {error && <p className="error">{error}</p>}
            {success && <p className="success">{success}</p>}

            <div className="memories-page-content">
                {loading ? (
                    <p className="memories-loading">Loading memories...</p>
                ) : memories.length === 0 ? (
                    <div className="memories-empty-state">
                        <p>No memories yet.</p>
                        <p>As you chat with the AI, it will remember useful information about you to provide more personalized responses.</p>
                    </div>
                ) : (
                    <>
                        <div className="memories-stats">
                            <span>{memories.length} memor{memories.length === 1 ? 'y' : 'ies'}</span>
                            <button
                                className="delete-all-memories-btn"
                                onClick={handleDeleteAllMemories}
                            >
                                Delete All Memories
                            </button>
                        </div>
                        <div className="memories-full-list">
                            {memories.map((memory) => (
                                <div key={memory.id} className="memory-item-full">
                                    <div className="memory-content-full">
                                        {memory.memory}
                                    </div>
                                    <div className="memory-meta">
                                        {memory.created_at && (
                                            <span className="memory-date">
                                                {new Date(memory.created_at).toLocaleDateString()}
                                            </span>
                                        )}
                                        <button
                                            className="memory-delete-btn-full"
                                            onClick={() => handleDeleteMemory(memory.id)}
                                            disabled={deletingMemory === memory.id}
                                        >
                                            {deletingMemory === memory.id ? 'Deleting...' : 'Delete'}
                                        </button>
                                    </div>
                                </div>
                            ))}
                        </div>
                    </>
                )}
            </div>
        </div>
    );
};

export default MemoriesPage;
