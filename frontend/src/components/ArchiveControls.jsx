import React, { useState, useEffect } from 'react';

const ArchiveControls = ({ onSave, onClear, projectNames = [] }) => {
    const [archiveName, setArchiveName] = useState('');
    const [selectedProject, setSelectedProject] = useState('General');
    const [newProjectName, setNewProjectName] = useState('');

    useEffect(() => {
        // If 'General' isn't in the list, but the list exists, default to the first project
        if (!projectNames.includes('General') && projectNames.length > 0) {
            setSelectedProject(projectNames[0]);
        } else {
            setSelectedProject('General');
        }
    }, [projectNames]);


    const handleSave = () => {
        const projectToSave = selectedProject === '__new__' ? newProjectName : selectedProject;
        if (selectedProject === '__new__' && !newProjectName.trim()) {
            alert('Please enter a name for the new project.');
            return;
        }
        onSave(archiveName, projectToSave);
        setArchiveName(''); // Clear input after saving
        if (selectedProject === '__new__') {
            setNewProjectName(''); // Clear new project name
        }
    };

    return (
        <div className="archive-controls">
            <input 
                type="text" 
                value={archiveName}
                onChange={(e) => setArchiveName(e.target.value)}
                placeholder="Optional: Name this chat..."
            />
            <select value={selectedProject} onChange={(e) => setSelectedProject(e.target.value)}>
                {projectNames.includes('General') || <option value="General">General</option>}
                {projectNames.map(name => (
                    <option key={name} value={name}>{name}</option>
                ))}
                <option value="__new__">New Project...</option>
            </select>
            {selectedProject === '__new__' && (
                <input
                    type="text"
                    value={newProjectName}
                    onChange={(e) => setNewProjectName(e.target.value)}
                    placeholder="New project name..."
                    autoFocus
                />
            )}
            <button onClick={handleSave} title="Save Chat">💾</button>
            <button onClick={onClear} title="Clear Memory">♻️</button>
        </div>
    );
};

export default ArchiveControls; 