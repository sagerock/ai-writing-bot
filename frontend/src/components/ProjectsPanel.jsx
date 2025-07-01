import React, { useState, useEffect, useRef } from 'react';
import { API_URL } from '../apiConfig';

const ProjectsPanel = ({ auth, onLoadArchive, onSelectDocument, onUploadSuccess }) => {
    const [projects, setProjects] = useState({});
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState('');
    const [uploadingProject, setUploadingProject] = useState(null);
    const fileInputRefs = useRef({});

    const fetchProjects = async () => {
        setLoading(true);
        setError('');
        try {
            const token = await auth.currentUser.getIdToken();
            const response = await fetch(`${API_URL}/projects`, {
                headers: { 'Authorization': `Bearer ${token}` }
            });

            if (!response.ok) {
                throw new Error('Failed to fetch projects.');
            }
            const data = await response.json();
            setProjects(data);
        } catch (err) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    };

    const handleFileUpload = async (event, projectName) => {
        const file = event.target.files[0];
        if (!file) return;
    
        setUploadingProject(projectName);
        const formData = new FormData();
        formData.append('file', file);
        formData.append('project_name', projectName);
    
        try {
            const token = await auth.currentUser.getIdToken();
            const response = await fetch(`${API_URL}/upload`, {
                method: 'POST',
                headers: { 'Authorization': `Bearer ${token}` },
                body: formData,
            });
    
            if (!response.ok) {
                throw new Error('File upload failed.');
            }
    
            const result = await response.json();
            
            if (onUploadSuccess) {
                onUploadSuccess(result.context_message);
            }
            fetchProjects(); // Refresh the list
    
        } catch (error) {
            setError("Upload failed.");
            console.error("Error uploading file:", error);
        } finally {
            setUploadingProject(null);
            // Clear the file input
            event.target.value = null;
        }
    };

    const handleDeleteDocument = async (filename) => {
        if (!window.confirm(`Are you sure you want to delete ${filename}? This cannot be undone.`)) {
            return;
        }

        try {
            const token = await auth.currentUser.getIdToken();
            const response = await fetch(`${API_URL}/document/${filename}`, {
                method: 'DELETE',
                headers: { 'Authorization': `Bearer ${token}` }
            });

            if (!response.ok) {
                const errData = await response.json();
                throw new Error(errData.detail || 'Failed to delete document.');
            }
            
            // Refresh the list after successful deletion
            fetchProjects();

        } catch (err) {
            alert(err.message);
        }
    };

    const handleDeleteChat = async (chatId) => {
        if (!window.confirm(`Are you sure you want to delete this chat? This cannot be undone.`)) {
            return;
        }

        try {
            const token = await auth.currentUser.getIdToken();
            const response = await fetch(`${API_URL}/archive/${chatId}`, {
                method: 'DELETE',
                headers: { 'Authorization': `Bearer ${token}` }
            });

            if (!response.ok) {
                const errData = await response.json();
                throw new Error(errData.detail || 'Failed to delete chat.');
            }
            
            // Refresh the list after successful deletion
            fetchProjects();

        } catch (err) {
            alert(err.message);
        }
    };

    const handleSelectDocument = async (doc) => {
        try {
            const token = await auth.currentUser.getIdToken();
            const response = await fetch(`${API_URL}/document/${encodeURIComponent(doc.filename)}`, {
                headers: { 'Authorization': `Bearer ${token}` }
            });
            if (!response.ok) {
                throw new Error('Failed to load document.');
            }
            const data = await response.json();
            const contextMessage = {
                role: 'context',
                content: data.content,
                display_text: `Loaded document: ${doc.filename}`
            };
            if (onSelectDocument) {
                onSelectDocument(contextMessage);
            }
        } catch (err) {
            alert(err.message);
        }
    };

    useEffect(() => {
        if (auth.currentUser) {
            fetchProjects();
        }
    }, [auth.currentUser]);

    // This allows the panel to be refreshed from the parent
    useEffect(() => {
        const handleRefresh = () => fetchProjects();
        window.addEventListener('refresh-projects', handleRefresh);
        return () => window.removeEventListener('refresh-projects', handleRefresh);
    }, []);

    const getFileInputRef = (projectName) => {
        if (!fileInputRefs.current[projectName]) {
            fileInputRefs.current[projectName] = React.createRef();
        }
        return fileInputRefs.current[projectName];
    };

    return (
        <div className="projects-panel">
            <div className="projects-header">
                <h2>Projects</h2>
                <div className="sidebar-controls">
                    <button onClick={fetchProjects} title="Refresh">🔄</button>
                </div>
            </div>
            <p className="info-text">
                Loading a chat will replace your current one. Documents are added to the current conversation.
            </p>
            {error && <p className="error">{error}</p>}
            {Object.keys(projects).length === 0 && !loading && <p>No projects found.</p>}
            
            <ul className="projects-list">
                {Object.entries(projects).map(([projectName, projectData]) => (
                    <li key={projectName}>
                        <details open>
                            <summary>
                                <span className="project-name">{projectName}</span>
                                <div className="project-controls">
                                    <button 
                                        onClick={(e) => {
                                            e.stopPropagation();
                                            getFileInputRef(projectName).current?.click();
                                        }} 
                                        disabled={uploadingProject === projectName}
                                        title="Upload Document"
                                        className="upload-btn"
                                    >
                                        {uploadingProject === projectName ? '⏳' : '📤'}
                                    </button>
                                    <input 
                                        type="file" 
                                        ref={getFileInputRef(projectName)}
                                        onChange={(e) => handleFileUpload(e, projectName)} 
                                        style={{ display: 'none' }} 
                                        disabled={uploadingProject === projectName}
                                        accept=".pdf,.txt,.md"
                                    />
                                </div>
                            </summary>
                            
                            <ul className="project-content">
                                {/* Documents */}
                                {projectData.documents?.map(doc => (
                                    <li key={`doc-${doc.filename}`} className="project-item document-item">
                                        <span className="item-icon">📄</span>
                                        <span className="item-name" onClick={() => handleSelectDocument(doc)}>
                                            {doc.filename}
                                        </span>
                                        <button className="delete-btn" onClick={() => handleDeleteDocument(doc.filename)}>🗑️</button>
                                    </li>
                                ))}
                                
                                {/* Chats */}
                                {projectData.chats?.map(chat => (
                                    <li key={`chat-${chat.id}`} className="project-item chat-item">
                                        <span className="item-icon">💬</span>
                                        <span className="item-name" onClick={() => onLoadArchive(chat.id)}>
                                            {chat.id.replace('.md', '')}
                                        </span>
                                        <button className="delete-btn" onClick={() => handleDeleteChat(chat.id)}>🗑️</button>
                                    </li>
                                ))}
                                
                                {/* Empty state */}
                                {(!projectData.documents || projectData.documents.length === 0) && 
                                 (!projectData.chats || projectData.chats.length === 0) && (
                                    <li className="empty-project">No documents or chats in this project</li>
                                )}
                            </ul>
                        </details>
                    </li>
                ))}
            </ul>
        </div>
    );
};

export default ProjectsPanel; 