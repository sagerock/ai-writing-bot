import React, { useState, useEffect } from 'react';
import { API_URL } from '../apiConfig';

const ArchivesPanel = ({ auth, archives, loading, error, onLoadArchive, onRefresh }) => {

    const handleDelete = async (archiveId) => {
        if (!window.confirm(`Are you sure you want to delete ${archiveId}?`)) {
            return;
        }

        try {
            const token = await auth.currentUser.getIdToken();
            const response = await fetch(`${API_URL}/archive/${archiveId}`, {
                method: 'DELETE',
                headers: { 'Authorization': `Bearer ${token}` }
            });

            if (!response.ok) {
                const errData = await response.json();
                throw new Error(errData.detail || 'Failed to delete archive.');
            }
            
            // Refresh the list after successful deletion
            onRefresh();

        } catch (err) {
            alert(err.message);
        }
    };
    
    return (
        <div className="archives-panel">
            <div className="archives-header">
                <h2>Saved Chats</h2>
                <div className="sidebar-controls">
                    {/* The refresh button is no longer needed here */}
                </div>
            </div>
            <p className="info-text">
                Loading a chat will replace your current one. Add documents after loading a chat.
            </p>
            {error && <p className="error">{error}</p>}
            {Object.keys(archives).length === 0 && !loading && <p>No saved chats.</p>}
            <ul className="archives-list">
                {Object.entries(archives).map(([project, chatList]) => (
                    <li key={project}>
                        <details open>
                            <summary>{project}</summary>
                            <ul>
                                {chatList.map(chat => (
                                    <li key={chat.id} className="archive-item">
                                        <span className="archive-name" onClick={() => onLoadArchive(chat.id)}>{chat.id}</span>
                                        <button className="delete-btn" onClick={() => handleDelete(chat.id)}>🗑️</button>
                                    </li>
                                ))}
                            </ul>
                        </details>
                    </li>
                ))}
            </ul>
        </div>
    );
};

export default ArchivesPanel; 