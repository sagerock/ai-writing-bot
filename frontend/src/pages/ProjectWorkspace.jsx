import { Fragment, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import WorkspaceHeader from '../components/WorkspaceHeader';
import { API_URL } from '../apiConfig';
import { renderMarkdown } from '../renderMarkdown';
import { useModelOptions } from '../useModelOptions';
import { applyDraftEdit, draftSections } from '../draftUtils';
import {
  createProjectChat,
  deleteProjectChat,
  deleteProjectSource,
  formatApiError,
  getProject,
  getProjectChat,
  getProjectSourceText,
  listProjectTemplates,
  listProjectDraftVersions,
  restoreProjectDraftVersion,
  saveProjectDraft,
  updateProject,
  updateProjectSourceLabel,
  uploadProjectSource,
} from '../projectApi';
import './Projects.css';

const HAIKU_MODEL = 'claude-haiku-4-5-20251001';
const HAIKU_SOURCE_LIMIT = 150_000;

const TEMPLATE_FALLBACK = {
  id: 'memo',
  label: 'Memo',
  brief_label: 'Project charge',
  primary_field: 'question',
  fields: [
    { key: 'question', label: 'Question presented' },
    { key: 'jurisdiction', label: 'Jurisdiction' },
    { key: 'audience', label: 'Audience' },
    { key: 'format_notes', label: 'Format' },
    { key: 'free_text', label: 'Notes' },
  ],
  brainstorm_actions: [
    { label: 'Identify issues', prompt: 'Identify the key legal and factual issues raised by the question presented and sources.' },
    { label: 'Summarize sources', prompt: 'Summarize each source separately, then explain how the sources relate to one another.' },
    { label: 'Outline memo', prompt: 'Create a well-structured outline for the memo, including the likely rule and application sections.' },
    { label: 'Test the analysis', prompt: 'Give me the strongest counterargument and identify the weakest assumptions in the likely analysis.' },
  ],
  write_actions: [
    { label: 'Draft Facts', prompt: 'Draft the Facts section as polished memorandum prose, using the source record and precise citations.' },
    { label: 'Draft Analysis', prompt: 'Draft the Analysis section as polished memorandum prose, addressing both the best argument and counterargument.' },
    { label: 'Draft whole memo', prompt: 'Draft the complete memorandum in the requested format, with a clear answer and source-grounded citations.' },
    { label: 'Strengthen target', prompt: 'Rewrite the selected target to make it more precise, concise, and persuasive without overstating the sources.' },
  ],
};

const formatDate = (value) => {
  if (!value) return '';
  return new Intl.DateTimeFormat('en-US', { month: 'short', day: 'numeric' }).format(new Date(value));
};

const formatTokens = (count = 0) => {
  if (count < 1_000) return `${count}`;
  return `${(count / 1_000).toFixed(count >= 100_000 ? 0 : 1)}k`;
};

const sourceLocation = (citation) => {
  if (citation.page) {
    return citation.page_end && citation.page_end !== citation.page
      ? `pp. ${citation.page}–${citation.page_end}`
      : `p. ${citation.page}`;
  }
  if (citation.paragraph) {
    return citation.paragraph_end && citation.paragraph_end !== citation.paragraph
      ? `¶¶ ${citation.paragraph}–${citation.paragraph_end}`
      : `¶ ${citation.paragraph}`;
  }
  return 'source';
};

function SourceText({ data }) {
  if (!data?.pages?.length) {
    return <pre className="source-viewer-text">{data?.text || ''}</pre>;
  }
  return (
    <div className="source-viewer-segments">
      {data.pages.map((entry, index) => {
        const location = entry.page || entry.paragraph || index + 1;
        const label = data.kind === 'page' ? `Page ${location}` : `Paragraph ${location}`;
        return (
          <section key={`${label}-${entry.start}`} id={`source-location-${location}`}>
            <div>{label}</div>
            <pre>{data.text.slice(entry.start, entry.end)}</pre>
          </section>
        );
      })}
    </div>
  );
}

export default function ProjectWorkspace({
  auth,
  user,
  isSubscriber,
  darkMode,
  onToggleDarkMode,
  onLogout,
}) {
  const { projectId } = useParams();
  const navigate = useNavigate();
  const modelOptions = useModelOptions().filter((option) => option.id !== 'auto');
  const [project, setProject] = useState(null);
  const [templates, setTemplates] = useState([TEMPLATE_FALLBACK]);
  const [selectedChatId, setSelectedChatId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [message, setMessage] = useState('');
  const [model, setModel] = useState('claude-sonnet-5');
  const [mode, setMode] = useState('brainstorm');
  const [draft, setDraft] = useState('');
  const [savedDraft, setSavedDraft] = useState('');
  const [draftVersions, setDraftVersions] = useState([]);
  const [draftView, setDraftView] = useState('edit');
  const [writeTarget, setWriteTarget] = useState('append');
  const [draftSelection, setDraftSelection] = useState(null);
  const [savingDraft, setSavingDraft] = useState(false);
  const [sourceViewer, setSourceViewer] = useState(null);
  const [editingSourceId, setEditingSourceId] = useState(null);
  const [sourceLabel, setSourceLabel] = useState('');
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState('');
  const [mobilePane, setMobilePane] = useState('chat');
  const abortRef = useRef(null);
  const chatEndRef = useRef(null);
  const draftEditorRef = useRef(null);

  const loadProject = useCallback(async ({ selectNewest = false } = {}) => {
    const data = await getProject(auth, projectId);
    setProject(data);
    setModel((current) => current || data.default_model);
    if (selectNewest && data.chats?.length) setSelectedChatId(data.chats[0].id);
    return data;
  }, [auth, projectId]);

  useEffect(() => {
    let active = true;
    const initialize = async () => {
      setLoading(true);
      setError('');
      try {
        const [data, templateData] = await Promise.all([
          getProject(auth, projectId),
          listProjectTemplates(auth).catch(() => [TEMPLATE_FALLBACK]),
        ]);
        if (!active) return;
        setProject(data);
        setTemplates(templateData);
        setModel(data.default_model || 'claude-sonnet-5');
        const initialDraft = data.draft?.markdown || '';
        setDraft(initialDraft);
        setSavedDraft(initialDraft);
        listProjectDraftVersions(auth, projectId).then((versions) => {
          if (active) setDraftVersions(versions);
        }).catch(() => {});
        if (data.chats?.length) {
          setSelectedChatId(data.chats[0].id);
        } else {
          const chat = await createProjectChat(auth, projectId, {
            title: 'New brainstorm',
            mode: 'brainstorm',
            model: data.default_model,
          });
          if (!active) return;
          setSelectedChatId(chat.id);
          setProject((current) => ({ ...current, chats: [chat] }));
        }
      } catch (loadError) {
        if (active) setError(loadError.message);
      } finally {
        if (active) setLoading(false);
      }
    };
    initialize();
    return () => {
      active = false;
      abortRef.current?.abort();
    };
  }, [auth, projectId]);

  useEffect(() => {
    if (!selectedChatId) return;
    let active = true;
    getProjectChat(auth, projectId, selectedChatId)
      .then((chat) => {
        if (!active) return;
        setMessages(chat.messages || []);
        if (chat.model) setModel(chat.model);
        if (chat.mode) setMode(chat.mode);
      })
      .catch((chatError) => active && setError(chatError.message));
    return () => { active = false; };
  }, [auth, projectId, selectedChatId]);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  useEffect(() => {
    if (draftView !== 'edit' || !draftEditorRef.current) return;
    const editor = draftEditorRef.current;
    editor.style.height = 'auto';
    editor.style.height = `${Math.max(editor.scrollHeight, window.innerHeight * 0.7)}px`;
  }, [draft, draftView]);

  useEffect(() => {
    const warnAboutUnsavedDraft = (event) => {
      if (draft === savedDraft) return;
      event.preventDefault();
      event.returnValue = '';
    };
    window.addEventListener('beforeunload', warnAboutUnsavedDraft);
    return () => window.removeEventListener('beforeunload', warnAboutUnsavedDraft);
  }, [draft, savedDraft]);

  useEffect(() => {
    if (!sourceViewer) return undefined;
    const closeOnEscape = (event) => {
      if (event.key === 'Escape') setSourceViewer(null);
    };
    window.addEventListener('keydown', closeOnEscape);
    return () => window.removeEventListener('keydown', closeOnEscape);
  }, [sourceViewer]);

  const sourcesByNumber = useMemo(() => Object.fromEntries(
    (project?.sources || []).map((source) => [source.source_num, source]),
  ), [project?.sources]);
  const sections = useMemo(() => draftSections(draft), [draft]);
  const draftWords = useMemo(() => draft.trim() ? draft.trim().split(/\s+/).length : 0, [draft]);
  const projectTemplate = templates.find((template) => template.id === project?.kind) || TEMPLATE_FALLBACK;
  const primaryBrief = project?.charge?.[projectTemplate.primary_field] || '';

  const haikuDisabled = (project?.total_source_tokens || 0) > HAIKU_SOURCE_LIMIT;

  const handleModelChange = async (event) => {
    const nextModel = event.target.value;
    setModel(nextModel);
    try {
      await updateProject(auth, projectId, { default_model: nextModel });
      setProject((current) => ({ ...current, default_model: nextModel }));
    } catch (updateError) {
      setError(updateError.message);
    }
  };

  const handleUpload = async (event) => {
    const files = Array.from(event.target.files || []);
    if (!files.length) return;
    setUploading(true);
    setError('');
    try {
      for (const file of files) await uploadProjectSource(auth, projectId, file);
      await loadProject();
    } catch (uploadError) {
      setError(uploadError.message);
    } finally {
      setUploading(false);
      event.target.value = '';
    }
  };

  const handleDeleteSource = async (source) => {
    if (!window.confirm(`Remove “${source.label}” from this project?`)) return;
    try {
      await deleteProjectSource(auth, projectId, source.id);
      await loadProject();
    } catch (deleteError) {
      setError(deleteError.message);
    }
  };

  const openSourceViewer = async (source, citation = null) => {
    if (!source) return;
    const location = citation?.page || citation?.paragraph || null;
    setSourceViewer({ source, citation, location, loading: true, data: null, error: '' });
    try {
      const data = await getProjectSourceText(auth, projectId, source.id, location);
      setSourceViewer((current) => current?.source.id === source.id && current.location === location
        ? { ...current, loading: false, data }
        : current);
    } catch (viewerError) {
      setSourceViewer((current) => current?.source.id === source.id && current.location === location
        ? { ...current, loading: false, error: viewerError.message }
        : current);
    }
  };

  const moveSourceViewer = (delta) => {
    if (!sourceViewer?.location) return;
    const maximum = sourceViewer.source.map_kind === 'page'
      ? sourceViewer.source.pages
      : sourceViewer.source.paragraphs;
    const nextLocation = sourceViewer.location + delta;
    if (nextLocation < 1 || (maximum && nextLocation > maximum)) return;
    openSourceViewer(sourceViewer.source, sourceViewer.source.map_kind === 'page'
      ? { page: nextLocation }
      : { paragraph: nextLocation });
  };

  const handleSourceLabelSave = async (event, source) => {
    event.preventDefault();
    event.stopPropagation();
    const nextLabel = sourceLabel.trim();
    if (!nextLabel) return;
    try {
      const updated = await updateProjectSourceLabel(auth, projectId, source.id, nextLabel);
      setProject((current) => ({
        ...current,
        sources: current.sources.map((item) => item.id === source.id ? updated : item),
      }));
      setEditingSourceId(null);
    } catch (labelError) {
      setError(labelError.message);
    }
  };

  const handleNewChat = async () => {
    try {
      const chat = await createProjectChat(auth, projectId, {
        title: `New ${mode === 'write' ? 'drafting' : 'brainstorm'} chat`,
        mode,
        model,
      });
      setProject((current) => ({ ...current, chats: [chat, ...(current.chats || [])] }));
      setSelectedChatId(chat.id);
      setMessages([]);
      setMobilePane('chat');
    } catch (chatError) {
      setError(chatError.message);
    }
  };

  const handleDeleteChat = async (event, chat) => {
    event.stopPropagation();
    if (!window.confirm(`Delete “${chat.title}”?`)) return;
    try {
      await deleteProjectChat(auth, projectId, chat.id);
      const remaining = (project.chats || []).filter((item) => item.id !== chat.id);
      setProject((current) => ({ ...current, chats: remaining }));
      if (selectedChatId === chat.id) {
        setSelectedChatId(remaining[0]?.id || null);
        setMessages([]);
      }
    } catch (deleteError) {
      setError(deleteError.message);
    }
  };

  const refreshDraftVersions = useCallback(async () => {
    const versions = await listProjectDraftVersions(auth, projectId);
    setDraftVersions(versions);
  }, [auth, projectId]);

  const saveDraft = async (nextDraft, reason) => {
    setSavingDraft(true);
    setError('');
    try {
      const saved = await saveProjectDraft(auth, projectId, nextDraft, reason);
      setDraft(saved.markdown);
      setSavedDraft(saved.markdown);
      setProject((current) => ({ ...current, draft: saved }));
      await refreshDraftVersions();
      return true;
    } catch (saveError) {
      setError(saveError.message);
      return false;
    } finally {
      setSavingDraft(false);
    }
  };

  const handleManualDraftSave = () => saveDraft(draft, 'manual save');

  const handleRestoreDraft = async (event) => {
    const version = Number(event.target.value);
    event.target.value = '';
    if (!version || !window.confirm(`Restore draft version ${version}? Your current draft will remain in version history.`)) return;
    setSavingDraft(true);
    try {
      if (draft !== savedDraft) {
        await saveProjectDraft(auth, projectId, draft, 'saved before version restore');
      }
      const restored = await restoreProjectDraftVersion(auth, projectId, version);
      setDraft(restored.markdown);
      setSavedDraft(restored.markdown);
      setProject((current) => ({ ...current, draft: restored }));
      await refreshDraftVersions();
    } catch (restoreError) {
      setError(restoreError.message);
    } finally {
      setSavingDraft(false);
    }
  };

  const handleApplyToDraft = async (assistantContent, messageIndex, target = writeTarget) => {
    const nextDraft = applyDraftEdit(draft, assistantContent, target, draftSelection);
    const applied = await saveDraft(
      nextDraft,
      `chat ${selectedChatId}, message ${messageIndex + 1}`,
    );
    if (applied) setMobilePane('draft');
  };

  const handleCopyDraft = async () => {
    try {
      await navigator.clipboard.writeText(draft);
    } catch {
      setError('The draft could not be copied to the clipboard.');
    }
  };

  const finishStream = useCallback((history, assistantContent, citations, responseMode, responseTarget) => {
    setMessages(history.concat([{
      role: 'assistant',
      content: assistantContent,
      citations,
      mode: responseMode,
      writeTarget: responseTarget,
    }]));
    setSending(false);
    loadProject().catch(() => {});
  }, [loadProject]);

  const sendMessage = async (content = message) => {
    const trimmed = content.trim();
    if (!trimmed || sending || !selectedChatId) return;
    const userMessage = { role: 'user', content: trimmed };
    const requestHistory = [...messages, userMessage].map(({ role, content: text }) => ({ role, content: text }));
    setMessages([...messages, userMessage, { role: 'assistant', content: '', streaming: true }]);
    setMessage('');
    setSending(true);
    setError('');
    abortRef.current = new AbortController();

    let responseText = '';
    let citations = [];
    let finished = false;
    const responseMode = mode;
    const responseTarget = writeTarget;
    const finish = () => {
      if (finished) return;
      finished = true;
      finishStream(requestHistory, responseText, citations, responseMode, responseTarget);
    };

    try {
      const token = await auth.currentUser.getIdToken();
      const response = await fetch(`${API_URL}/chat_stream`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          history: requestHistory,
          model,
          search_web: false,
          search_docs: false,
          temperature: 0.7,
          project_id: projectId,
          chat_id: selectedChatId,
          mode: responseMode,
          write_target: responseMode === 'write' ? (
            responseTarget === 'selection' && draftSelection?.text
              ? `Selected text: ${draftSelection.text.slice(0, 450)}`
              : sections.find((section) => section.id === responseTarget)?.heading
                || (responseTarget === 'whole' ? 'the whole draft' : 'the end of the draft')
          ) : null,
        }),
        signal: abortRef.current.signal,
      });
      if (!response.ok) {
        const payload = await response.json().catch(() => null);
        throw new Error(formatApiError(payload));
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      while (true) {
        const { done, value } = await reader.read();
        if (done) { finish(); break; }
        buffer += decoder.decode(value, { stream: true });
        let boundary;
        while ((boundary = buffer.indexOf('\n\n')) >= 0) {
          const event = buffer.slice(0, boundary);
          buffer = buffer.slice(boundary + 2);
          if (!event.startsWith('data: ')) continue;
          const raw = event.slice(6).trim();
          if (!raw) continue;
          if (raw === '[DONE]') { finish(); return; }
          const parsed = JSON.parse(raw);
          if (typeof parsed === 'string') {
            if (parsed.startsWith('ERROR:')) throw new Error(parsed.slice(6).trim());
            responseText += parsed;
            setMessages((current) => current.map((item) => (
              item.streaming ? { ...item, content: responseText } : item
            )));
          } else if (parsed?.citations) {
            citations = parsed.citations;
          }
        }
      }
    } catch (streamError) {
      if (streamError.name === 'AbortError') {
        finish();
      } else {
        setMessages(requestHistory);
        setError(streamError.message || 'The response could not be generated.');
        setSending(false);
      }
    } finally {
      abortRef.current = null;
    }
  };

  const handleSubmit = (event) => {
    event.preventDefault();
    sendMessage();
  };

  if (loading) {
    return <div className={`project-loading ${darkMode ? 'dark' : ''}`}>Opening project…</div>;
  }

  if (!project) {
    return (
      <div className={`project-loading ${darkMode ? 'dark' : ''}`}>
        <p>{error || 'Project not found.'}</p>
        <button onClick={() => navigate('/projects')}>Back to projects</button>
      </div>
    );
  }

  return (
    <div className={`App project-shell ${darkMode ? 'dark' : ''}`}>
      <WorkspaceHeader
        user={user}
        isSubscriber={isSubscriber}
        darkMode={darkMode}
        onToggleDarkMode={onToggleDarkMode}
        onLogout={onLogout}
      />
      <div className="workspace-titlebar">
        <div>
          <Link to="/projects">Projects</Link><span>/</span><strong>{project.name}</strong><i>{projectTemplate.label}</i>
        </div>
        <div className="workspace-mode"><span>{mode === 'write' ? 'Write' : 'Brainstorm'}</span><small>{draftWords} draft words</small></div>
      </div>

      {error && <div className="project-error workspace-error" role="alert">{error}</div>}

      <div className="workspace-mobile-tabs" role="tablist">
        <button className={mobilePane === 'sources' ? 'active' : ''} onClick={() => setMobilePane('sources')}>Project</button>
        <button className={mobilePane === 'chat' ? 'active' : ''} onClick={() => setMobilePane('chat')}>{mode === 'write' ? 'Write' : 'Brainstorm'}</button>
        <button className={mobilePane === 'draft' ? 'active' : ''} onClick={() => setMobilePane('draft')}>Draft</button>
      </div>

      <main className="project-workspace">
        <aside className={`workspace-sidebar ${mobilePane === 'sources' ? 'mobile-active' : ''}`}>
          <section className="charge-card">
            <p className="project-eyebrow">{projectTemplate.brief_label}</p>
            <h2>{primaryBrief}</h2>
            <dl>
              {projectTemplate.fields
                .filter((field) => field.key !== projectTemplate.primary_field && project.charge?.[field.key])
                .map((field) => (
                  <Fragment key={field.key}>
                    <dt>{field.label}</dt><dd>{project.charge[field.key]}</dd>
                  </Fragment>
                ))}
            </dl>
          </section>

          <section className="workspace-sidebar-section">
            <div className="workspace-section-heading">
              <h2>Sources <span>{project.sources?.length || 0}</span></h2>
              <label className={`project-upload-button ${uploading ? 'disabled' : ''}`}>
                {uploading ? 'Adding…' : '+ Add'}
                <input type="file" multiple disabled={uploading} accept=".pdf,.txt,.md,.docx,.csv" onChange={handleUpload} />
              </label>
            </div>
            <div className="source-list">
              {(project.sources || []).map((source) => (
                <div className="source-row" key={source.id}>
                  <span className="source-number">{source.source_num}</span>
                  {editingSourceId === source.id ? (
                    <form className="source-label-form" onSubmit={(event) => handleSourceLabelSave(event, source)}>
                      <input
                        value={sourceLabel}
                        onChange={(event) => setSourceLabel(event.target.value)}
                        onClick={(event) => event.stopPropagation()}
                        autoFocus
                        maxLength={160}
                        aria-label="Source label"
                      />
                      <button title="Save label">✓</button>
                    </form>
                  ) : (
                    <button className="source-copy" onClick={() => openSourceViewer(source)} title="View extracted source text">
                      <strong>{source.label}</strong>
                      <small>{source.pages ? `${source.pages} pages` : `${source.paragraphs || 0} paragraphs`} · {formatTokens(source.estimated_tokens)} tokens</small>
                    </button>
                  )}
                  <div className="source-row-actions">
                    <button
                      onClick={() => { setEditingSourceId(source.id); setSourceLabel(source.label); }}
                      title="Rename source"
                    >✎</button>
                    <button onClick={() => handleDeleteSource(source)} title="Remove source">×</button>
                  </div>
                </div>
              ))}
              {!project.sources?.length && <p className="sidebar-empty">Add source files to ground every answer.</p>}
            </div>
            <div className={`context-banner ${project.context_mode === 'retrieval' ? 'retrieval' : ''}`}>
              <strong>{project.context_mode === 'retrieval' ? 'Retrieval mode' : 'Full-source context'}</strong>
              <span>{formatTokens(project.total_source_tokens)} estimated source tokens</span>
              {project.context_mode === 'retrieval' && <small>Roma will retrieve the most relevant passages for each question.</small>}
            </div>
          </section>

          <section className="workspace-sidebar-section chat-history-section">
            <div className="workspace-section-heading">
              <h2>Chats <span>{project.chats?.length || 0}</span></h2>
              <button className="project-text-button" onClick={handleNewChat}>+ New</button>
            </div>
            <div className="project-chat-list">
              {(project.chats || []).map((chat) => (
                <button
                  key={chat.id}
                  className={chat.id === selectedChatId ? 'active' : ''}
                  onClick={() => { setSelectedChatId(chat.id); setMobilePane('chat'); }}
                >
                  <span><strong>{chat.title}</strong><small>{chat.message_count || 0} messages · {formatDate(chat.updated_at)}</small></span>
                  <i onClick={(event) => handleDeleteChat(event, chat)} title="Delete chat">×</i>
                </button>
              ))}
            </div>
          </section>
        </aside>

        <section className={`brainstorm-pane ${mobilePane === 'chat' ? 'mobile-active' : ''}`}>
          <div className="brainstorm-toolbar">
            <div className="mode-toggle" aria-label="Conversation mode">
              <button className={mode === 'brainstorm' ? 'active' : ''} onClick={() => setMode('brainstorm')}>Brainstorm</button>
              <button className={mode === 'write' ? 'active' : ''} onClick={() => setMode('write')}>Write</button>
            </div>
            <div className="brainstorm-toolbar-controls">
              <span className="source-context-status"><i className="status-dot" />Sources included</span>
              <label>
                Model
                <select value={model} onChange={handleModelChange}>
                  {modelOptions.map((option) => (
                    <option key={option.id} value={option.id} disabled={option.id === HAIKU_MODEL && haikuDisabled}>
                      {option.name}{option.id === HAIKU_MODEL && haikuDisabled ? ' — source limit exceeded' : ''}
                    </option>
                  ))}
                </select>
              </label>
            </div>
          </div>

          <div className="brainstorm-messages">
            {messages.length === 0 && (
              <div className="brainstorm-welcome">
                <p className="project-eyebrow">{mode === 'write' ? 'Draft from the record' : 'Start with the record'}</p>
                <h1>{mode === 'write' ? 'What should Roma draft?' : 'What should we work through?'}</h1>
                <p>Roma has the {projectTemplate.brief_label.toLowerCase()}, current draft, and {project.sources?.length || 'no'} source{project.sources?.length === 1 ? '' : 's'} in context.</p>
                <div className="quick-action-grid">
                  {(mode === 'write' ? projectTemplate.write_actions : projectTemplate.brainstorm_actions).map(({ label, prompt }) => (
                    <button key={label} onClick={() => sendMessage(prompt)} disabled={sending}>{label}<span>→</span></button>
                  ))}
                </div>
              </div>
            )}
            {messages.map((item, index) => (
              <article className={`brainstorm-message ${item.role}`} key={`${item.role}-${index}`}>
                <div className="message-author">{item.role === 'user' ? 'You' : 'Roma'}</div>
                <div className="message-body" dangerouslySetInnerHTML={{ __html: renderMarkdown(item.content) }} />
                {item.streaming && <span className="stream-cursor" />}
                {item.citations?.length > 0 && (
                  <div className="message-citations" aria-label="Sources cited">
                    {item.citations.map((citation, citationIndex) => (
                      <button
                        key={`${citation.source_id}-${citationIndex}`}
                        onClick={() => openSourceViewer(sourcesByNumber[citation.source_num], citation)}
                        title="Open cited source location"
                      >
                        [{citation.source_num}] {sourcesByNumber[citation.source_num]?.label || 'Source'} · {sourceLocation(citation)}
                      </button>
                    ))}
                  </div>
                )}
                {item.role === 'assistant' && item.content && !item.streaming && (item.mode === 'write' || (!item.mode && mode === 'write')) && (
                  <button
                    className="apply-draft-button"
                    onClick={() => handleApplyToDraft(item.content, index, item.writeTarget || writeTarget)}
                    disabled={savingDraft}
                  >
                    {savingDraft ? 'Applying…' : 'Apply to draft'}
                  </button>
                )}
              </article>
            ))}
            <div ref={chatEndRef} />
          </div>

          <form className="brainstorm-composer" onSubmit={handleSubmit}>
            {mode === 'write' && (
              <label className="write-target-control">
                Target
                <select value={writeTarget} onChange={(event) => setWriteTarget(event.target.value)}>
                  <option value="append">Append to draft</option>
                  <option value="whole">Replace whole draft</option>
                  {draftSelection?.text && <option value="selection">Replace selected text</option>}
                  {sections.map((section) => <option key={section.id} value={section.id}>Replace “{section.heading}”</option>)}
                </select>
              </label>
            )}
            <textarea
              value={message}
              onChange={(event) => setMessage(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === 'Enter' && !event.shiftKey) {
                  event.preventDefault();
                  sendMessage();
                }
              }}
              rows={3}
              placeholder={mode === 'write'
                ? `Ask Roma to draft or revise this ${projectTemplate.label.toLowerCase()}…`
                : 'Ask about the sources, test an idea, or build an outline…'}
              disabled={sending || !selectedChatId}
            />
            <div>
              <small>Enter to send · Shift+Enter for a new line</small>
              {sending ? (
                <button type="button" className="project-secondary-button" onClick={() => abortRef.current?.abort()}>Stop</button>
              ) : (
                <button className="project-primary-button" disabled={!message.trim()}>Send</button>
              )}
            </div>
          </form>
        </section>

        <aside className={`draft-pane ${mobilePane === 'draft' ? 'mobile-active' : ''}`}>
          <div className="draft-toolbar">
            <div>
              <strong>Draft</strong>
              <span>{draftWords} words · v{project.draft?.version || 0}</span>
            </div>
            <div className="draft-toolbar-actions">
              <div className="draft-view-toggle">
                <button className={draftView === 'edit' ? 'active' : ''} onClick={() => setDraftView('edit')}>Edit</button>
                <button className={draftView === 'preview' ? 'active' : ''} onClick={() => setDraftView('preview')}>Preview</button>
              </div>
              <button className="project-text-button" onClick={handleCopyDraft} disabled={!draft}>Copy</button>
            </div>
          </div>
          <div className="draft-document">
            {draftView === 'edit' ? (
              <textarea
                ref={draftEditorRef}
                value={draft}
                onChange={(event) => setDraft(event.target.value)}
                onSelect={(event) => {
                  const { selectionStart: start, selectionEnd: end, value } = event.currentTarget;
                  setDraftSelection(end > start ? { start, end, text: value.slice(start, end) } : null);
                }}
                placeholder={'# Legal Memorandum\n\nStart writing here, or ask Roma to draft a section.'}
                aria-label="Memo draft in Markdown"
              />
            ) : (
              <div className="draft-preview" dangerouslySetInnerHTML={{ __html: renderMarkdown(draft || '*The draft is empty.*') }} />
            )}
          </div>
          <div className="draft-footer">
            <select defaultValue="" onChange={handleRestoreDraft} disabled={savingDraft || draftVersions.length === 0} aria-label="Restore a draft version">
              <option value="" disabled>Version history</option>
              {draftVersions.map((version) => (
                <option key={version.version} value={version.version}>
                  v{version.version} · {version.reason} · {formatDate(version.saved_at)}
                </option>
              ))}
            </select>
            <span className={draft !== savedDraft ? 'draft-dirty' : ''}>{draft !== savedDraft ? 'Unsaved changes' : 'Saved'}</span>
            <button className="project-primary-button" onClick={handleManualDraftSave} disabled={savingDraft || draft === savedDraft}>
              {savingDraft ? 'Saving…' : 'Save draft'}
            </button>
          </div>
        </aside>
      </main>

      {sourceViewer && (
        <div
          className="source-viewer-backdrop"
          role="presentation"
          onMouseDown={(event) => {
            if (event.target === event.currentTarget) setSourceViewer(null);
          }}
        >
          <section className="source-viewer" role="dialog" aria-modal="true" aria-labelledby="source-viewer-title">
            <header>
              <div>
                <p className="project-eyebrow">Source [{sourceViewer.source.source_num}]</p>
                <h2 id="source-viewer-title">{sourceViewer.source.label}</h2>
                <span>{sourceViewer.source.filename}</span>
              </div>
              <button onClick={() => setSourceViewer(null)} title="Close source viewer">×</button>
            </header>
            <div className="source-viewer-locationbar">
              <span>
                {sourceViewer.location
                  ? `${sourceViewer.source.map_kind === 'page' ? 'Page' : 'Paragraph'} ${sourceViewer.location}`
                  : 'Complete extracted text'}
              </span>
              {sourceViewer.location && (
                <div>
                  <button onClick={() => moveSourceViewer(-1)} disabled={sourceViewer.location <= 1}>← Previous</button>
                  <button
                    onClick={() => moveSourceViewer(1)}
                    disabled={sourceViewer.location >= (sourceViewer.source.pages || sourceViewer.source.paragraphs || Infinity)}
                  >Next →</button>
                  <button onClick={() => openSourceViewer(sourceViewer.source)}>View all</button>
                </div>
              )}
            </div>
            <div className="source-viewer-content">
              {sourceViewer.loading ? (
                <div className="source-viewer-state">Loading source text…</div>
              ) : sourceViewer.error ? (
                <div className="project-error">{sourceViewer.error}</div>
              ) : (
                <SourceText data={sourceViewer.data} />
              )}
            </div>
            <footer>
              Extracted text may differ from the original file’s visual formatting.
              {sourceViewer.citation?.span?.text && <strong>Citation: {sourceViewer.citation.span.text}</strong>}
            </footer>
          </section>
        </div>
      )}
    </div>
  );
}
