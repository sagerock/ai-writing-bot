import React, { useState, useEffect, useRef } from 'react';
import { API_URL } from '../apiConfig';

const ProjectsPanel = ({ auth, onLoadArchive, onSelectDocument, onUploadSuccess }) => {
    const [projects, setProjects] = useState({});
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState('');
    const [uploadingProject, setUploadingProject] = useState(null);
    const [creatingNewProject, setCreatingNewProject] = useState(false);
    const [newProjectName, setNewProjectName] = useState('');
    const fileInputRefs = useRef({});
    const newProjectFileInputRef = useRef();

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

    const handleNewProjectUpload = async (event) => {
        const file = event.target.files[0];
        if (!file || !newProjectName.trim()) return;
    
        const projectName = newProjectName.trim();
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
            setCreatingNewProject(false);
            setNewProjectName('');
    
        } catch (error) {
            setError("Upload failed.");
            console.error("Error uploading file:", error);
        } finally {
            setUploadingProject(null);
            // Clear the file input
            event.target.value = null;
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
                    <button onClick={() => setCreatingNewProject(true)} title="Create New Project">➕</button>
                    <button onClick={fetchProjects} title="Refresh">🔄</button>
                </div>
            </div>
            <p className="info-text">
                Loading a chat will replace your current one. Documents are added to the current conversation.
            </p>
            {error && <p className="error">{error}</p>}
            {Object.keys(projects).length === 0 && !loading && <p>No projects found.</p>}
            
            {/* New Project Creation Modal */}
            {creatingNewProject && (
                <div className="modal-backdrop" onClick={() => setCreatingNewProject(false)}>
                    <div className="modal-content" onClick={(e) => e.stopPropagation()}>
                        <div className="modal-header">
                            <h3>Create New Project</h3>
                            <button className="close-modal-btn" onClick={() => setCreatingNewProject(false)}>×</button>
                        </div>
                        <div className="new-project-form">
                            <input
                                type="text"
                                placeholder="Enter project name"
                                value={newProjectName}
                                onChange={(e) => setNewProjectName(e.target.value)}
                                onKeyPress={(e) => e.key === 'Enter' && newProjectName.trim() && newProjectFileInputRef.current?.click()}
                                autoFocus
                            />
                            <div className="new-project-actions">
                                <button 
                                    onClick={() => newProjectFileInputRef.current?.click()}
                                    disabled={!newProjectName.trim() || uploadingProject === newProjectName}
                                >
                                    {uploadingProject === newProjectName ? 'Uploading...' : 'Upload First File'}
                                </button>
                                <button onClick={() => {
                                    setCreatingNewProject(false);
                                    setNewProjectName('');
                                }}>Cancel</button>
                            </div>
                            <input 
                                type="file" 
                                ref={newProjectFileInputRef}
                                onChange={(e) => handleNewProjectUpload(e)} 
                                style={{ display: 'none' }} 
                                disabled={uploadingProject === newProjectName}
                                accept=".pdf,.txt,.md"
                            />
                        </div>
                    </div>
                </div>
            )}
            
            <ul className="projects-list">
                {Object.entries(projects).map(([projectName, projectData]) => (
                    <li key={projectName}>
                        <details>
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