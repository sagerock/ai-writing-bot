const chatWindow = document.getElementById('chat-window');
const chatForm = document.getElementById('chat-form');
const userInput = document.getElementById('user-input');
const stopBtn = document.getElementById('stop-btn');

let abortController = new AbortController();

// Model selection elements
const modelSelect = document.getElementById('model-select');
const webSearchCheckbox = document.getElementById('web-search-checkbox');

// File upload elements
const fileInput = document.getElementById('file-input');
const uploadBtn = document.getElementById('upload-btn');
const uploadStatus = document.getElementById('upload-status');
const stagedFilesList = document.getElementById('staged-files-list');
const addToChatBtn = document.getElementById('add-to-chat-btn');

let stagedFiles = [];

// Archive elements
// Archive and clear memory elements
const archiveBtn = document.getElementById('archive-btn');
const clearMemoryBtn = document.getElementById('clear-memory-btn');
const archiveStatus = document.getElementById('archive-status');
const archiveNameInput = document.getElementById('archive-name-input');
const projectSelect = document.getElementById('project-select');
const newProjectInput = document.getElementById('new-project-input');

// Archives panel elements
const archivesList = document.getElementById('archives-list');
const refreshArchivesBtn = document.getElementById('refresh-archives-btn');
const archivesStatus = document.getElementById('archives-status');

// Save/load model selection from localStorage
const savedModel = localStorage.getItem('chatbot_model');
if (savedModel && modelSelect) modelSelect.value = savedModel;
if (modelSelect) {
    modelSelect.addEventListener('change', () => {
        localStorage.setItem('chatbot_model', modelSelect.value);
    });
}
function getSelectedModel() {
    return modelSelect ? modelSelect.value : 'gpt-3.5-turbo';
}

function appendMessage(sender, text) {
    const msgDiv = document.createElement('div');
    msgDiv.className = `message ${sender}`;
    const bubble = document.createElement('div');
    bubble.className = 'bubble';
    if (sender === 'bot' || sender === 'ai') { // Handle 'ai' type from history
        bubble.innerHTML = marked.parse(text);
    } else { // 'user' or 'human'
        bubble.textContent = text;
    }
    msgDiv.appendChild(bubble);
    chatWindow.appendChild(msgDiv);
    chatWindow.scrollTop = chatWindow.scrollHeight;
}

// Handle chat form submission and keyboard events
async function handleFormSubmit(e) {
    if (e) e.preventDefault();
    const text = userInput.value.trim();
    if (!text) return;

    appendMessage('user', text);
    userInput.value = '';
    userInput.style.height = 'auto'; // Reset height

    // Add a placeholder for the bot's response
    const placeholder = document.createElement('div');
    placeholder.className = 'message bot';
    const bubble = document.createElement('div');
    bubble.className = 'bubble';
    bubble.textContent = '...';
    placeholder.appendChild(bubble);
    chatWindow.appendChild(placeholder);
    chatWindow.scrollTop = chatWindow.scrollHeight;

    // Enable stop button and create new AbortController
    stopBtn.disabled = false;
    abortController = new AbortController();

    try {
        const res = await fetch('/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
                message: text, 
                model: getSelectedModel(),
                search_web: webSearchCheckbox.checked
            }),
            signal: abortController.signal // Pass the signal to fetch
        });
        if (!res.body) {
            bubble.textContent = 'Streaming not supported by your browser.';
            return;
        }
        const reader = res.body.getReader();
        const decoder = new TextDecoder('utf-8');
        let botText = '';

        while (true) {
            const { value, done } = await reader.read();
            if (done) break;
            botText += decoder.decode(value, { stream: true });
            bubble.innerHTML = marked.parse(botText);
            chatWindow.scrollTop = chatWindow.scrollHeight;
        }
    } catch (err) {
        if (err.name === 'AbortError') {
            bubble.textContent = 'Request stopped.';
        } else {
            bubble.textContent = 'Error: Could not reach server.';
        }
    } finally {
        // Disable the stop button once generation is complete or stopped
        stopBtn.disabled = true;
    }
}

chatForm.addEventListener('submit', handleFormSubmit);
userInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        handleFormSubmit();
    }
});

// Auto-resize textarea
userInput.addEventListener('input', () => {
    userInput.style.height = 'auto';
    userInput.style.height = (userInput.scrollHeight) + 'px';
});

// Handle stop button click
stopBtn.addEventListener('click', () => {
    abortController.abort();
    stopBtn.disabled = true;
});

// --- File Staging and Upload Logic ---

fileInput.addEventListener('change', () => {
    // Add new files to the stagedFiles array, avoiding duplicates
    for (const file of fileInput.files) {
        if (!stagedFiles.some(f => f.name === file.name)) {
            stagedFiles.push(file);
        }
    }
    renderStagedFiles();
    // Clear the input so the change event fires even if the same file is selected again
    fileInput.value = ''; 
});

function renderStagedFiles() {
    stagedFilesList.innerHTML = '';
    if (stagedFiles.length === 0) {
        addToChatBtn.style.display = 'none';
        return;
    }

    stagedFiles.forEach((file, index) => {
        const li = document.createElement('li');
        
        const checkbox = document.createElement('input');
        checkbox.type = 'checkbox';
        checkbox.id = `file-${index}`;
        checkbox.checked = true; // Default to selected
        checkbox.dataset.index = index;
        
        const label = document.createElement('label');
        label.htmlFor = `file-${index}`;
        label.textContent = file.name;
        
        const removeBtn = document.createElement('button');
        removeBtn.textContent = 'x';
        removeBtn.className = 'remove-file-btn';
        removeBtn.onclick = () => {
            stagedFiles.splice(index, 1);
            renderStagedFiles();
        };

        li.appendChild(checkbox);
        li.appendChild(label);
        li.appendChild(removeBtn);
        stagedFilesList.appendChild(li);
    });

    addToChatBtn.style.display = 'inline-block';
}

addToChatBtn.addEventListener('click', async () => {
    const selectedCheckboxes = stagedFilesList.querySelectorAll('input[type="checkbox"]:checked');
    if (selectedCheckboxes.length === 0) {
        uploadStatus.textContent = 'Please select files to add.';
        uploadStatus.style.color = 'red';
        return;
    }

    uploadStatus.textContent = 'Uploading selected files...';
    uploadStatus.style.color = 'black';
    let successCount = 0;
    let errorCount = 0;

    for (const checkbox of selectedCheckboxes) {
        const fileIndex = parseInt(checkbox.dataset.index, 10);
        const file = stagedFiles[fileIndex];

        const formData = new FormData();
        formData.append('file', file);
        formData.append('model', getSelectedModel());
        
        try {
            const res = await fetch('/upload', {
                method: 'POST',
                body: formData
            });
            const data = await res.json();
            if (res.ok) {
                successCount++;
            } else {
                errorCount++;
                console.error(`Upload failed for ${file.name}:`, data.error);
            }
        } catch (err) {
            errorCount++;
            console.error(`Upload error for ${file.name}:`, err);
        }
    }

    if (errorCount > 0) {
        uploadStatus.textContent = `Finished: ${successCount} uploaded, ${errorCount} failed.`;
        uploadStatus.style.color = 'red';
    } else {
        uploadStatus.textContent = `${successCount} file(s) added to chat context.`;
        uploadStatus.style.color = 'green';
    }

    // Clear the staged files that were successfully uploaded
    stagedFiles = stagedFiles.filter((file, index) => {
        return !Array.from(selectedCheckboxes).some(cb => parseInt(cb.dataset.index, 10) === index);
    });
    renderStagedFiles();
});

// Handle chat archive
if (archiveBtn) {
    archiveBtn.addEventListener('click', async () => {
        archiveStatus.textContent = 'Archiving...';
        archiveStatus.style.color = 'black';
        
        let projectName;
        if (projectSelect.value === '__new__') {
            projectName = newProjectInput.value.trim();
            if (!projectName) {
                archiveStatus.textContent = 'New project name cannot be empty.';
                archiveStatus.style.color = 'red';
                return;
            }
        } else {
            projectName = projectSelect.value;
        }

        try {
            const model = modelSelect.value;
            const archiveName = archiveNameInput.value.trim();

            const response = await fetch('/archive', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ 
                    model: model,
                    archive_name: archiveName,
                    project_name: projectName
                })
            });
            const data = await response.json();
            if (response.ok) {
                archiveStatus.textContent = data.message || 'Chat archived successfully.';
                archiveStatus.style.color = 'green';
                fetchArchives(); // Refresh the archives list and project dropdown
                newProjectInput.value = '';
                newProjectInput.style.display = 'none';
            } else {
                archiveStatus.textContent = data.error || 'Archiving failed.';
                archiveStatus.style.color = 'red';
            }
        } catch (err) {
            archiveStatus.textContent = 'Archive error.';
            archiveStatus.style.color = 'red';
        }
    });
}

// Handle clear memory
if (clearMemoryBtn) {
    clearMemoryBtn.addEventListener('click', async () => {
        if (confirm('Are you sure you want to clear the conversation memory? This cannot be undone.')) {
            archiveStatus.textContent = 'Clearing memory...';
            archiveStatus.style.color = 'black';
            try {
                const response = await fetch('/clear_memory', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({})
                });
                const data = await response.json();
                if (response.ok) {
                    archiveStatus.textContent = data.message || 'Memory cleared successfully.';
                    archiveStatus.style.color = 'green';
                    chatWindow.innerHTML = ''; // Clear the chat window
                } else {
                    archiveStatus.textContent = data.error || 'Failed to clear memory.';
                    archiveStatus.style.color = 'red';
                }
            } catch (err) {
                archiveStatus.textContent = 'Error clearing memory.';
                archiveStatus.style.color = 'red';
            }
        }
    });
}

// --- Archives Panel Logic ---
async function fetchArchives() {
    archivesStatus.textContent = 'Loading...';
    archivesStatus.style.color = 'black';
    try {
        const response = await fetch(`/archives?t=${new Date().getTime()}`);
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const projects = await response.json();
        
        // Populate archives list
        archivesList.innerHTML = '';
        if (Object.keys(projects).length === 0) {
            archivesStatus.textContent = 'No saved chats found.';
            archivesStatus.style.color = '#6c757d';
        } else {
            archivesStatus.textContent = '';
            const sortedProjects = Object.keys(projects).sort();
            for (const projectName of sortedProjects) {
                const projectFiles = projects[projectName];
                
                const details = document.createElement('details');
                details.open = true; // Default to open
                
                const summary = document.createElement('summary');
                summary.textContent = projectName;
                details.appendChild(summary);

                const fileList = document.createElement('ul');
                projectFiles.forEach(filename => {
                    const li = document.createElement('li');
                    li.textContent = filename.replace('.md', '');
                    li.dataset.filename = filename;
                    li.dataset.project = projectName; // Store project name
                    li.addEventListener('click', () => loadArchive(projectName, filename));
                    fileList.appendChild(li);
                });
                
                details.appendChild(fileList);
                archivesList.appendChild(details);
            }
        }

        // Populate project dropdown
        const selectedProject = projectSelect.value;
        projectSelect.innerHTML = ''; // Clear previous options
        
        const generalOption = document.createElement('option');
        generalOption.value = 'General';
        generalOption.textContent = 'General';
        projectSelect.appendChild(generalOption);

        const sortedProjectNames = Object.keys(projects).sort();
        sortedProjectNames.forEach(name => {
            if (name !== 'General') {
                const option = document.createElement('option');
                option.value = name;
                option.textContent = name;
                projectSelect.appendChild(option);
            }
        });

        const newOption = document.createElement('option');
        newOption.value = '__new__';
        newOption.textContent = 'New Project...';
        projectSelect.appendChild(newOption);

        // Restore previous selection if it still exists
        projectSelect.value = sortedProjectNames.includes(selectedProject) ? selectedProject : 'General';

    } catch (err) {
        archivesStatus.textContent = 'Error loading archives.';
        archivesStatus.style.color = 'red';
        console.error('Fetch archives error:', err);
    }
}

async function loadArchive(projectName, filename) {
    if (!confirm(`Are you sure you want to load the archive "${filename}" from project "${projectName}"? This will replace your current chat history.`)) {
        return;
    }
    archivesStatus.textContent = `Loading ${filename}...`;
    try {
        const response = await fetch('/load_archive', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ project_name: projectName, filename: filename })
        });
        const data = await response.json();
        if (response.ok) {
            // Reload conversation history into the chat window
            await loadChatHistory();
            archivesStatus.textContent = `Loaded ${filename}.`;
            archivesStatus.style.color = 'green';
        } else {
            archivesStatus.textContent = `Error: ${data.error}`;
            archivesStatus.style.color = 'red';
            console.error('Failed to load archive:', data.error);
        }
    } catch (err) {
        archivesStatus.textContent = 'Error loading archive.';
        archivesStatus.style.color = 'red';
        console.error('Failed to load archive:', err);
    }
}

async function loadChatHistory() {
    try {
        const response = await fetch('/history');
        const data = await response.json();

        if (response.ok && data.history) {
            chatWindow.innerHTML = '';
            data.history.forEach(msg => {
                // Adjust for 'human' type from backend memory
                const sender = msg.type === 'human' ? 'user' : msg.type;
                appendMessage(sender, msg.content);
            });
        }
    } catch (err) {
        console.error("Could not load chat history:", err);
    }
}

if (refreshArchivesBtn) {
    refreshArchivesBtn.addEventListener('click', fetchArchives);
}

projectSelect.addEventListener('change', () => {
    if (projectSelect.value === '__new__') {
        newProjectInput.style.display = 'inline-block';
        newProjectInput.focus();
    } else {
        newProjectInput.style.display = 'none';
        newProjectInput.value = '';
    }
});

// Initial setup on page load
document.addEventListener('DOMContentLoaded', () => {
    fetchArchives();
    loadChatHistory();
});
