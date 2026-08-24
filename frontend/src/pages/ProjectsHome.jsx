import { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import WorkspaceHeader from '../components/WorkspaceHeader';
import { API_URL } from '../apiConfig';
import {
  archiveProject,
  createProject,
  listProjects,
  uploadProjectSource,
} from '../projectApi';
import './Projects.css';

const EMPTY_CHARGE = {
  question: '',
  jurisdiction: '',
  audience: '',
  format_notes: '',
  free_text: '',
};

const formatDate = (value) => {
  if (!value) return 'No activity yet';
  return new Intl.DateTimeFormat('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  }).format(new Date(value));
};

export default function ProjectsHome({
  auth,
  user,
  isSubscriber,
  darkMode,
  onToggleDarkMode,
  onLogout,
  onOpenQuickChat,
}) {
  const navigate = useNavigate();
  const [projects, setProjects] = useState([]);
  const [quickChats, setQuickChats] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [showCreate, setShowCreate] = useState(false);
  const [creating, setCreating] = useState(false);
  const [name, setName] = useState('');
  const [charge, setCharge] = useState(EMPTY_CHARGE);
  const [files, setFiles] = useState([]);

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const [projectData, token] = await Promise.all([
        listProjects(auth),
        auth.currentUser.getIdToken(),
      ]);
      setProjects(projectData);
      const response = await fetch(`${API_URL}/archives`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (response.ok) {
        const archiveGroups = await response.json();
        const flattened = Object.values(archiveGroups).flat().sort((left, right) => (
          new Date(right.archivedAt || 0) - new Date(left.archivedAt || 0)
        ));
        setQuickChats(flattened.slice(0, 12));
      }
    } catch (loadError) {
      setError(loadError.message);
    } finally {
      setLoading(false);
    }
  }, [auth]);

  useEffect(() => {
    load();
  }, [load]);

  const updateCharge = (field, value) => {
    setCharge((current) => ({ ...current, [field]: value }));
  };

  const resetForm = () => {
    setName('');
    setCharge(EMPTY_CHARGE);
    setFiles([]);
  };

  const handleCreate = async (event) => {
    event.preventDefault();
    setCreating(true);
    setError('');
    try {
      const project = await createProject(auth, {
        name,
        kind: 'memo',
        charge,
      });
      for (const file of files) {
        await uploadProjectSource(auth, project.id, file);
      }
      resetForm();
      setShowCreate(false);
      navigate(`/projects/${project.id}`);
    } catch (createError) {
      setError(createError.message);
    } finally {
      setCreating(false);
    }
  };

  const handleArchive = async (event, projectId) => {
    event.stopPropagation();
    if (!window.confirm('Archive this project? Its data will be preserved.')) return;
    try {
      await archiveProject(auth, projectId);
      setProjects((current) => current.filter((project) => project.id !== projectId));
    } catch (archiveError) {
      setError(archiveError.message);
    }
  };

  return (
    <div className={`App project-shell ${darkMode ? 'dark' : ''}`}>
      <WorkspaceHeader
        user={user}
        isSubscriber={isSubscriber}
        darkMode={darkMode}
        onToggleDarkMode={onToggleDarkMode}
        onLogout={onLogout}
      />
      <main className="projects-home">
        <section className="projects-hero">
          <div>
            <p className="project-eyebrow">Document workspaces</p>
            <h1>Projects</h1>
            <p>Bring the charge, source record, and every research conversation together.</p>
          </div>
          <button className="project-primary-button" onClick={() => setShowCreate(true)}>
            New memo project
          </button>
        </section>

        {error && <div className="project-error" role="alert">{error}</div>}

        <section aria-labelledby="project-list-heading">
          <div className="project-section-heading">
            <h2 id="project-list-heading">Your projects</h2>
            <button className="project-text-button" onClick={load}>Refresh</button>
          </div>
          {loading ? (
            <div className="project-empty">Loading projects…</div>
          ) : projects.length === 0 ? (
            <button className="project-empty project-empty-action" onClick={() => setShowCreate(true)}>
              <strong>Start your first memo</strong>
              <span>Add a question presented and the source record.</span>
            </button>
          ) : (
            <div className="project-card-grid">
              {projects.map((project) => (
                <article
                  className="project-card"
                  key={project.id}
                  onClick={() => navigate(`/projects/${project.id}`)}
                >
                  <div className="project-card-topline">
                    <span className="project-kind">Memo</span>
                    <button
                      className="project-icon-button"
                      onClick={(event) => handleArchive(event, project.id)}
                      title="Archive project"
                    >
                      ···
                    </button>
                  </div>
                  <h3>{project.name}</h3>
                  <p className="project-question">{project.charge?.question}</p>
                  <div className="project-card-meta">
                    <span>{project.source_count} source{project.source_count === 1 ? '' : 's'}</span>
                    <span>{project.chat_count} chat{project.chat_count === 1 ? '' : 's'}</span>
                    <span>{project.draft_word_count} draft words</span>
                  </div>
                  <p className="project-updated">Updated {formatDate(project.updated_at)}</p>
                </article>
              ))}
            </div>
          )}
        </section>

        <section className="quick-chat-section" aria-labelledby="quick-chat-heading">
          <div className="project-section-heading">
            <div>
              <h2 id="quick-chat-heading">Quick chats</h2>
              <p>Your existing General conversations stay right where they are.</p>
            </div>
            <button className="project-secondary-button" onClick={() => navigate('/chat')}>
              New quick chat
            </button>
          </div>
          {quickChats.length === 0 ? (
            <div className="project-empty">No saved quick chats yet.</div>
          ) : (
            <div className="quick-chat-list">
              {quickChats.map((chat) => (
                <button key={chat.id} onClick={() => onOpenQuickChat(chat.id)}>
                  <span>
                    <strong>{chat.title}</strong>
                    <small>{chat.preview}</small>
                  </span>
                  <time>{formatDate(chat.archivedAt)}</time>
                </button>
              ))}
            </div>
          )}
        </section>
      </main>

      {showCreate && (
        <div className="project-modal-backdrop" role="presentation">
          <div className="project-modal" role="dialog" aria-modal="true" aria-labelledby="new-project-title">
            <div className="project-modal-heading">
              <div>
                <p className="project-eyebrow">New workspace</p>
                <h2 id="new-project-title">Create a memo project</h2>
              </div>
              <button className="project-icon-button" onClick={() => setShowCreate(false)}>✕</button>
            </div>
            {error && <div className="project-error" role="alert">{error}</div>}
            <form onSubmit={handleCreate}>
              <label>
                Project name
                <input value={name} onChange={(event) => setName(event.target.value)} required maxLength={160} />
              </label>
              <label>
                Question presented <span className="required-label">Required</span>
                <textarea
                  value={charge.question}
                  onChange={(event) => updateCharge('question', event.target.value)}
                  required
                  rows={3}
                />
              </label>
              <div className="project-form-grid">
                <label>
                  Jurisdiction
                  <input value={charge.jurisdiction} onChange={(event) => updateCharge('jurisdiction', event.target.value)} />
                </label>
                <label>
                  Audience
                  <input value={charge.audience} onChange={(event) => updateCharge('audience', event.target.value)} />
                </label>
              </div>
              <label>
                Format notes
                <input
                  value={charge.format_notes}
                  onChange={(event) => updateCharge('format_notes', event.target.value)}
                  placeholder="Short answer first, 2,000 words, formal tone…"
                />
              </label>
              <label>
                Additional instructions
                <textarea
                  value={charge.free_text}
                  onChange={(event) => updateCharge('free_text', event.target.value)}
                  rows={3}
                />
              </label>
              <label>
                Initial sources <span className="optional-label">Optional</span>
                <input
                  type="file"
                  multiple
                  accept=".pdf,.txt,.md,.docx,.csv"
                  onChange={(event) => setFiles(Array.from(event.target.files || []))}
                />
                {files.length > 0 && <small>{files.length} file{files.length === 1 ? '' : 's'} selected</small>}
              </label>
              <div className="project-modal-actions">
                <button type="button" className="project-text-button" onClick={() => setShowCreate(false)}>
                  Cancel
                </button>
                <button className="project-primary-button" disabled={creating}>
                  {creating ? 'Creating project…' : 'Create project'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
