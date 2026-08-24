import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import WorkspaceHeader from '../components/WorkspaceHeader';
import { API_URL } from '../apiConfig';
import { renderMarkdown } from '../renderMarkdown';
import { useModelOptions } from '../useModelOptions';
import {
  createProjectChat,
  deleteProjectChat,
  deleteProjectSource,
  formatApiError,
  getProject,
  getProjectChat,
  updateProject,
  uploadProjectSource,
} from '../projectApi';
import './Projects.css';

const HAIKU_MODEL = 'claude-haiku-4-5-20251001';
const HAIKU_SOURCE_LIMIT = 150_000;

const QUICK_ACTIONS = [
  ['Identify issues', 'Identify the key legal and factual issues raised by the question presented and sources.'],
  ['Summarize sources', 'Summarize each source separately, then explain how the sources relate to one another.'],
  ['Outline memo', 'Create a well-structured outline for the memo, including the likely rule and application sections.'],
  ['Test the analysis', 'Give me the strongest counterargument and identify the weakest assumptions in the likely analysis.'],
];

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
  const [selectedChatId, setSelectedChatId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [message, setMessage] = useState('');
  const [model, setModel] = useState('claude-sonnet-5');
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState('');
  const [mobilePane, setMobilePane] = useState('chat');
  const abortRef = useRef(null);
  const chatEndRef = useRef(null);

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
        const data = await getProject(auth, projectId);
        if (!active) return;
        setProject(data);
        setModel(data.default_model || 'claude-sonnet-5');
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
      })
      .catch((chatError) => active && setError(chatError.message));
    return () => { active = false; };
  }, [auth, projectId, selectedChatId]);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const sourcesByNumber = useMemo(() => Object.fromEntries(
    (project?.sources || []).map((source) => [source.source_num, source]),
  ), [project?.sources]);

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

  const handleNewChat = async () => {
    try {
      const chat = await createProjectChat(auth, projectId, {
        title: 'New brainstorm',
        mode: 'brainstorm',
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

  const finishStream = useCallback((history, assistantContent, citations) => {
    setMessages(history.concat([{ role: 'assistant', content: assistantContent, citations }]));
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
    const finish = () => {
      if (finished) return;
      finished = true;
      finishStream(requestHistory, responseText, citations);
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
          mode: 'brainstorm',
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
          <Link to="/projects">Projects</Link><span>/</span><strong>{project.name}</strong>
        </div>
        <div className="workspace-mode"><span>Brainstorm</span><small>Draft workspace comes next</small></div>
      </div>

      {error && <div className="project-error workspace-error" role="alert">{error}</div>}

      <div className="workspace-mobile-tabs" role="tablist">
        <button className={mobilePane === 'sources' ? 'active' : ''} onClick={() => setMobilePane('sources')}>Project</button>
        <button className={mobilePane === 'chat' ? 'active' : ''} onClick={() => setMobilePane('chat')}>Brainstorm</button>
      </div>

      <main className="project-workspace">
        <aside className={`workspace-sidebar ${mobilePane === 'sources' ? 'mobile-active' : ''}`}>
          <section className="charge-card">
            <p className="project-eyebrow">Question presented</p>
            <h2>{project.charge?.question}</h2>
            <dl>
              {project.charge?.jurisdiction && <><dt>Jurisdiction</dt><dd>{project.charge.jurisdiction}</dd></>}
              {project.charge?.audience && <><dt>Audience</dt><dd>{project.charge.audience}</dd></>}
              {project.charge?.format_notes && <><dt>Format</dt><dd>{project.charge.format_notes}</dd></>}
              {project.charge?.free_text && <><dt>Notes</dt><dd>{project.charge.free_text}</dd></>}
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
                  <span className="source-copy">
                    <strong>{source.label}</strong>
                    <small>{source.pages ? `${source.pages} pages` : `${source.paragraphs || 0} paragraphs`} · {formatTokens(source.estimated_tokens)} tokens</small>
                  </span>
                  <button onClick={() => handleDeleteSource(source)} title="Remove source">×</button>
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
            <div><span className="status-dot" />Project sources included</div>
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

          <div className="brainstorm-messages">
            {messages.length === 0 && (
              <div className="brainstorm-welcome">
                <p className="project-eyebrow">Start with the record</p>
                <h1>What should we work through?</h1>
                <p>Roma has the question presented and {project.sources?.length || 'no'} source{project.sources?.length === 1 ? '' : 's'} in context.</p>
                <div className="quick-action-grid">
                  {QUICK_ACTIONS.map(([label, prompt]) => (
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
                      <span key={`${citation.source_id}-${citationIndex}`}>
                        [{citation.source_num}] {sourcesByNumber[citation.source_num]?.label || 'Source'} · {sourceLocation(citation)}
                      </span>
                    ))}
                  </div>
                )}
              </article>
            ))}
            <div ref={chatEndRef} />
          </div>

          <form className="brainstorm-composer" onSubmit={handleSubmit}>
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
              placeholder="Ask about the sources, test an argument, or build an outline…"
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
      </main>
    </div>
  );
}
