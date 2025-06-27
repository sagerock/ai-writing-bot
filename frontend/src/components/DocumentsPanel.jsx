import React, { useState, useEffect, useRef } from 'react';
import { API_URL } from '../apiConfig';

const DocumentsPanel = ({ auth, onSelectDocument, onUploadSuccess }) => {
    const [documents, setDocuments] = useState([]);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState('');
    const fileInputRef = useRef(null);

    const fetchDocuments = async () => {
        setLoading(true);
        setError('');
        try {
            const token = await auth.currentUser.getIdToken();
            const response = await fetch(`${API_URL}/documents`, {
                headers: { 'Authorization': `Bearer ${token}` }
            });

            if (!response.ok) {
                throw new Error('Failed to fetch documents.');
            }
            const data = await response.json();
            setDocuments(data);
        } catch (err) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    };

    const handleFileUpload = async (event) => {
        const file = event.target.files[0];
        if (!file) return;
    
        setLoading(true);
        const formData = new FormData();
        formData.append('file', file);
    
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
          fetchDocuments(); // Refresh the list
    
        } catch (error) {
            setError("Upload failed.");
            console.error("Error uploading file:", error);
        } finally {
          setLoading(false);
          // Clear the file input
          event.target.value = null;
        }
    };

    const handleDelete = async (filename) => {
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
            fetchDocuments();

        } catch (err) {
            alert(err.message);
        }
    };

    useEffect(() => {
        if (auth.currentUser) {
            fetchDocuments();
        }
    }, [auth.currentUser]);

    // This allows the panel to be refreshed from the parent
    useEffect(() => {
        const handleRefresh = () => fetchDocuments();
        window.addEventListener('refresh-documents', handleRefresh);
        return () => window.removeEventListener('refresh-documents', handleRefresh);
    }, []);

    return (
        <div className="documents-panel">
            <h3>
                My Documents
                <button onClick={() => fileInputRef.current.click()} disabled={loading} title="Upload File">
                    📤
                </button>
            </h3>
            <input 
                type="file" 
                ref={fileInputRef}
                onChange={handleFileUpload} 
                style={{ display: 'none' }} 
                disabled={loading}
                accept=".pdf,.txt,.md"
            />
            {error && <p className="error">{error}</p>}
            {documents.length === 0 && !loading && <p className="no-documents">No documents uploaded.</p>}
            <ul className="documents-list">
                {documents.map(doc => (
                    <li key={doc.filename}>
                        <span className="doc-name" onClick={() => onSelectDocument(doc)}>{doc.filename}</span>
                        <button className="delete-btn" onClick={() => handleDelete(doc.filename)}>🗑️</button>
                    </li>
                ))}
            </ul>
        </div>
    );
};

export default DocumentsPanel; 