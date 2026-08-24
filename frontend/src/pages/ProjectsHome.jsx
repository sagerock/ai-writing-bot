import { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import WorkspaceHeader from '../components/WorkspaceHeader';
import { API_URL } from '../apiConfig';
import {
  archiveProject,
  createProject,
  listProjectTemplates,
  listProjects,
  uploadProjectSource,
} from '../projectApi';
import './Projects.css';

const MEMO_FALLBACK = {
  id: 'memo',
  label: 'Memo',
  description: 'Analyze a legal question against a source record.',
  primary_field: 'question',
  fields: [
    { key: 'question', label: 'Question presented', required: true, multiline: true, max_length: 5000 },
    { key: 'jurisdiction', label: 'Jurisdiction', max_length: 500 },
    { key: 'audience', label: 'Audience', max_length: 500 },
    { key: 'format_notes', label: 'Format notes', max_length: 2000 },
    { key: 'free_text', label: 'Additional instructions', multiline: true, max_length: 10000 },
  ],
};

const emptyCharge = (template) => Object.fromEntries(template.fields.map((field) => [field.key, '']));

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
  const [templates, setTemplates] = useState([MEMO_FALLBACK]);
  const [kind, setKind] = useState('memo');
  const [name, setName] = useState('');
  const [charge, setCharge] = useState(() => emptyCharge(MEMO_FALLBACK));
  const [files, setFiles] = useState([]);
  const selectedTemplate = templates.find((template) => template.id === kind) || MEMO_FALLBACK;
  const templatesById = Object.fromEntries(templates.map((template) => [template.id, template]));

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const [projectData, templateData, token] = await Promise.all([
        listProjects(auth),
        listProjectTemplates(auth).catch(() => [MEMO_FALLBACK]),
        auth.currentUser.getIdToken(),
      ]);
      setProjects(projectData);
      setTemplates(templateData);
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
    setKind('memo');
    setName('');
    setCharge(emptyCharge(templates.find((template) => template.id === 'memo') || MEMO_FALLBACK));
    setFiles([]);
  };

  const handleKindChange = (nextKind) => {
    const template = templates.find((item) => item.id === nextKind) || MEMO_FALLBACK;
    setKind(nextKind);
    setCharge(emptyCharge(template));
  };

  const handleCreate = async (event) => {
    event.preventDefault();
    setCreating(true);
    setError('');
    try {
      const project = await createProject(auth, {
        name,
        kind,
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
            <p>Bring the brief, source record, conversations, and living draft together.</p>
          </div>
          <button className="project-primary-button" onClick={() => setShowCreate(true)}>
            New project
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
              <strong>Start your first project</strong>
              <span>Choose a template, describe the goal, and add the source record.</span>
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
                    <span className="project-kind">{templatesById[project.kind]?.label || project.kind || 'Project'}</span>
                    <button
                      className="project-icon-button"
                      onClick={(event) => handleArchive(event, project.id)}
                      title="Archive project"
                    >
                      ···
                    </button>
                  </div>
                  <h3>{project.name}</h3>
                  <p className="project-question">
                    {project.charge?.[templatesById[project.kind]?.primary_field] || project.charge?.question || project.charge?.objective}
                  </p>
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
                <h2 id="new-project-title">Create a {selectedTemplate.label.toLowerCase()} project</h2>
              </div>
              <button className="project-icon-button" onClick={() => setShowCreate(false)}>✕</button>
            </div>
            {error && <div className="project-error" role="alert">{error}</div>}
            <form onSubmit={handleCreate}>
              <fieldset className="project-type-picker">
                <legend>Project type</legend>
                <div>
                  {templates.map((template) => (
                    <button
                      type="button"
                      key={template.id}
                      className={template.id === kind ? 'active' : ''}
                      onClick={() => handleKindChange(template.id)}
                    >
                      <strong>{template.label}</strong>
                      <span>{template.description}</span>
                    </button>
                  ))}
                </div>
              </fieldset>
              <label>
                Project name
                <input value={name} onChange={(event) => setName(event.target.value)} required maxLength={160} />
              </label>
              <div className="project-dynamic-fields">
                {selectedTemplate.fields.map((field) => (
                  <label key={field.key} className={field.multiline ? 'wide' : ''}>
                    <span>{field.label} {field.required && <i>Required</i>}</span>
                    {field.multiline ? (
                      <textarea
                        value={charge[field.key] || ''}
                        onChange={(event) => updateCharge(field.key, event.target.value)}
                        required={field.required}
                        maxLength={field.max_length}
                        placeholder={field.placeholder || ''}
                        rows={field.required ? 3 : 2}
                      />
                    ) : (
                      <input
                        value={charge[field.key] || ''}
                        onChange={(event) => updateCharge(field.key, event.target.value)}
                        required={field.required}
                        maxLength={field.max_length}
                        placeholder={field.placeholder || ''}
                      />
                    )}
                  </label>
                ))}
              </div>
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
