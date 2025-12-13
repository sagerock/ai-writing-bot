import React, { useState, useRef, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { marked } from 'marked';
import ChatControls from './ChatControls';
import ArchiveControls from './ArchiveControls';
import SimplifiedActions from './SimplifiedActions';
import NeuralLogPanel from './NeuralLogPanel';
import { API_URL } from '../apiConfig';

// Configure marked to treat single line breaks as <br> tags (GitHub-style)
marked.setOptions({
  gfm: true,
  breaks: true,
});

// Model options for the selector
const MODEL_OPTIONS = [
  { id: 'auto', name: 'Auto (Smart Routing)', category: 'auto' },
  { id: 'gpt-5-nano-2025-08-07', name: 'GPT-5 Nano', category: 'OpenAI' },
  { id: 'gpt-5-mini-2025-08-07', name: 'GPT-5 Mini', category: 'OpenAI' },
  { id: 'gpt-5-2025-08-07', name: 'GPT-5', category: 'OpenAI' },
  { id: 'gpt-5-pro-2025-10-06', name: 'GPT-5 Pro', category: 'OpenAI' },
  { id: 'gpt-5.1-2025-11-13', name: 'GPT-5.1', category: 'OpenAI' },
  { id: 'gpt-5.2', name: 'GPT-5.2', category: 'OpenAI' },
  { id: 'gpt-5.2-pro', name: 'GPT-5.2 Pro', category: 'OpenAI' },
  { id: 'claude-sonnet-4-5', name: 'Claude Sonnet 4.5', category: 'Anthropic' },
  { id: 'claude-opus-4-5', name: 'Claude Opus 4.5', category: 'Anthropic' },
  { id: 'gemini-3-pro-preview', name: 'Gemini 3 Pro', category: 'Google' },
  { id: 'gemini-2.5-pro', name: 'Gemini 2.5 Pro', category: 'Google' },
  { id: 'gemini-2.5-flash', name: 'Gemini 2.5 Flash', category: 'Google' },
  { id: 'gemini-2.0-flash', name: 'Gemini 2.0 Flash', category: 'Google' },
];

const getModelDisplayName = (modelId) => {
  const model = MODEL_OPTIONS.find(m => m.id === modelId);
  return model ? model.name : modelId;
};

const Chat = ({
  auth,
  history,
  setHistory,
  projectNames,
  onSaveSuccess,
  simplifiedMode = true,
  defaultModel = 'auto',
  defaultTemperature = 0.7
}) => {
  const [message, setMessage] = useState('');
  const [loading, setLoading] = useState(false);
  const [model, setModel] = useState(defaultModel);
  const [searchWeb, setSearchWeb] = useState(false);
  const [temperature, setTemperature] = useState(defaultTemperature);
  const abortControllerRef = useRef(null);
  const [copied, setCopied] = useState({});
  const [forceRerender, setForceRerender] = useState(0);
  const chatWindowRef = useRef(null);
  const [showNeuralLog, setShowNeuralLog] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [searchDocs, setSearchDocs] = useState(false);
  const fileInputRef = useRef(null);
  const textareaRef = useRef(null);
  const [routedModel, setRoutedModel] = useState(null); // Tracks auto-routed model
  const [showModelSelector, setShowModelSelector] = useState(false); // Model picker dropdown
  const [feedback, setFeedback] = useState({}); // Tracks feedback per message index
  const [sessionId] = useState(() => `chat_${Date.now()}`); // Unique ID for this chat session

  // Update model/temperature when defaults change from settings
  useEffect(() => {
    setModel(defaultModel);
  }, [defaultModel]);

  useEffect(() => {
    setTemperature(defaultTemperature);
  }, [defaultTemperature]);

  // Auto-scroll to bottom when new messages are added
  useEffect(() => {
    if (chatWindowRef.current) {
      chatWindowRef.current.scrollTop = chatWindowRef.current.scrollHeight;
    }
  }, [history, forceRerender]);

  // Auto-resize textarea as user types
  const autoResizeTextarea = () => {
    const textarea = textareaRef.current;
    if (textarea) {
      textarea.style.height = 'auto';
      textarea.style.height = Math.min(textarea.scrollHeight, 200) + 'px';
    }
  };

  useEffect(() => {
    autoResizeTextarea();
  }, [message]);

  const handleCopy = (text, index) => {
    navigator.clipboard.writeText(text).then(() => {
        setCopied({ [index]: true });
        setTimeout(() => {
            setCopied(prev => {
                const newCopied = {...prev};
                delete newCopied[index];
                return newCopied;
            });
        }, 2000);
    }).catch(err => {
        console.error('Failed to copy text: ', err);
        alert('Failed to copy text.');
    });
  };

  const handleFeedback = async (messageIndex, rating, messageContent) => {
    // Don't allow changing feedback once given
    if (feedback[messageIndex]) return;

    try {
      const token = await auth.currentUser.getIdToken();
      const messageId = `${Date.now()}-${messageIndex}`; // Unique ID for this feedback

      await fetch(`${API_URL}/feedback`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
          message_id: messageId,
          rating: rating,
          model: routedModel ? routedModel.routed_model : model,
          routed_category: routedModel ? routedModel.routed_category : null,
          message_snippet: messageContent.substring(0, 200)
        }),
      });

      // Mark feedback as given
      setFeedback(prev => ({ ...prev, [messageIndex]: rating }));
    } catch (error) {
      console.error('Failed to submit feedback:', error);
    }
  };

  const handleSendMessage = async () => {
    if (!message.trim() || loading) return;

    const userMessage = { role: 'user', content: message };
    const newHistory = [...history, userMessage];
    setHistory(newHistory);
    setMessage('');
    setLoading(true);
    setRoutedModel(null); // Clear previous routed model

    abortControllerRef.current = new AbortController();

    try {
      const token = await auth.currentUser.getIdToken();

      const response = await fetch(`${API_URL}/chat_stream`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
          history: newHistory,
          model: model,
          search_web: searchWeb,
          search_docs: searchDocs,
          temperature: temperature,
        }),
        signal: abortControllerRef.current.signal,
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'An error occurred');
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let assistantResponse = '';
      setHistory(prev => [...prev, { role: 'assistant', content: '', streaming: true }]);
      let buffer = '';

      const processStream = async () => {
        while (true) {
          const { done, value } = await reader.read();
          if (done) {
            const finalHistory = newHistory.concat([{ role: 'assistant', content: assistantResponse }]);
            setHistory(finalHistory);
            setLoading(false);
            setForceRerender(f => f + 1);
            autoSaveConversation(finalHistory);
            break;
          }

          buffer += decoder.decode(value, { stream: true });
          
          let msgEndIndex;
          while ((msgEndIndex = buffer.indexOf('\n\n')) >= 0) {
            const message = buffer.slice(0, msgEndIndex);
            buffer = buffer.slice(msgEndIndex + 2);

            if (message.startsWith('data: ')) {
              const dataString = message.substring(6).trim();
              if (!dataString) continue;

              if (dataString === '[DONE]') {
                const finalHistory = newHistory.concat([{ role: 'assistant', content: assistantResponse }]);
                setHistory(finalHistory);
                setLoading(false);
                setForceRerender(f => f + 1);
                autoSaveConversation(finalHistory);
                return;
              }

              // Check for error messages first
              if (dataString.startsWith('ERROR:')) {
                setHistory(prev => prev.map(msg => msg.streaming ? { ...msg, content: dataString, streaming: false } : msg));
                setLoading(false);
                setError(dataString);
                setForceRerender(f => f + 1);
                return;
              }

              try {
                const parsed = JSON.parse(dataString);

                // Check if this is routing info from auto mode
                if (parsed && typeof parsed === 'object' && parsed.routed_model) {
                  setRoutedModel(parsed);
                  console.log('Auto-routed to:', parsed.routed_model, '(' + parsed.routed_category + ')');
                  // Don't add routing info to the response
                  continue;
                }

                // Regular token (string)
                assistantResponse += parsed;
                setHistory(prev => prev.map(msg => msg.streaming ? { ...msg, content: assistantResponse } : msg));

              } catch (e) {
                console.error("Failed to parse JSON from stream:", dataString, e);
                // If it's not JSON and not an error, treat it as a plain text token
                if (!dataString.includes('SyntaxError')) {
                  assistantResponse += dataString;
                  setHistory(prev => prev.map(msg => msg.streaming ? { ...msg, content: assistantResponse } : msg));
                }
              }
            }
          }
        }
      };
      
      await processStream();

    } catch (error) {
      console.error("Error sending message:", error);
      if (error.name !== 'AbortError') {
        setHistory(prev => [...prev, { role: 'assistant', content: `Sorry, I encountered an error: ${error.message}` }]);
      }
      setLoading(false);
    }
  };

  const handleStop = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
  };

  // Auto-save conversation after each response
  const autoSaveConversation = async (updatedHistory) => {
    if (updatedHistory.length < 2) return; // Need at least one exchange

    try {
      const token = await auth.currentUser.getIdToken();
      const sessionDate = new Date(parseInt(sessionId.split('_')[1]));
      const timestamp = sessionDate.toISOString().slice(0, 16).replace('T', ' ');

      // Save to archives for later retrieval
      await fetch(`${API_URL}/archive`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
          history: updatedHistory,
          model: model,
          archive_name: `Chat ${timestamp}`,
          project_name: 'General',
        }),
      });

      // Save to mem0 for AI memory
      await fetch(`${API_URL}/save_memory`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
          history: updatedHistory,
          model: model,
          search_web: false,
          temperature: temperature,
        }),
      });
    } catch (error) {
      console.error('Failed to auto-save conversation:', error);
    }
  };

  const handleSave = async (archiveName, projectName) => {
    if (history.length === 0) {
        alert("Cannot save an empty chat.");
        return;
    }
    try {
        const token = await auth.currentUser.getIdToken();
        await fetch(`${API_URL}/archive`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify({
                history: history,
                model: model,
                archive_name: archiveName,
                project_name: projectName,
            }),
        });
        alert('Chat archived successfully!');
        if (onSaveSuccess) {
            onSaveSuccess();
        }
    } catch (error) {
        console.error("Error archiving chat:", error);
        alert('Failed to archive chat.');
    }
  };

  const handleFileUpload = async (event) => {
    const file = event.target.files[0];
    if (!file) return;

    setIsUploading(true);
    const formData = new FormData();
    formData.append('file', file);

    try {
      const token = await auth.currentUser.getIdToken();
      // Use quick upload - just extracts text, no storage/indexing
      const response = await fetch(`${API_URL}/upload_quick`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}` },
        body: formData,
      });

      if (!response.ok) {
        throw new Error('File upload failed.');
      }

      const result = await response.json();

      // Add context message to chat with the extracted text
      if (result.text) {
        setHistory(prev => [...prev, {
          role: 'context',
          content: result.text,
          display_text: `Uploaded: ${result.filename}`
        }]);
      }

    } catch (error) {
      console.error("Error uploading file:", error);
      alert('Failed to upload file.');
    } finally {
      setIsUploading(false);
      // Clear the file input
      event.target.value = null;
    }
  };

  // Simplified mode - ChatGPT-style centered layout
  if (simplifiedMode) {
    const hasMessages = history.length > 0;

    return (
      <div className={`chat-simplified ${hasMessages ? 'has-messages' : 'empty'}`}>
        {/* Upload overlay */}
        {isUploading && (
          <div className="upload-overlay">
            <span className="spinner"></span>
            <p>Uploading document...</p>
          </div>
        )}

        {/* Neural Log Panel - only when toggled */}
        {showNeuralLog && (
          <NeuralLogPanel
            currentModel={model}
            currentTemperature={temperature}
            searchWeb={searchWeb}
          />
        )}

        {/* Messages - scrollable area */}
        {hasMessages && (
          <div className="chat-messages" ref={chatWindowRef}>
            {history.map((msg, index) => (
              <div key={index} className={`message ${msg.role}`}>
                {msg.role === 'context' ? (
                  <p><em>{msg.display_text}</em></p>
                ) : msg.role === 'assistant' ? (
                  <>
                    {msg.streaming ? (
                      <pre style={{ whiteSpace: 'pre-wrap', fontFamily: 'inherit' }}>{msg.content}</pre>
                    ) : (
                      <div dangerouslySetInnerHTML={{ __html: marked.parse(msg.content) }} />
                    )}
                    {msg.content && !msg.streaming && (
                      <div className="message-actions">
                        <button
                          className="copy-btn"
                          onClick={() => handleCopy(msg.content, index)}
                          title="Copy to clipboard"
                        >
                          {copied[index] ? '✅' : '📋'}
                        </button>
                        <button
                          className={`feedback-btn ${feedback[index] === 'up' ? 'active' : ''}`}
                          onClick={() => handleFeedback(index, 'up', msg.content)}
                          title="Good response"
                          disabled={feedback[index]}
                        >
                          👍
                        </button>
                        <button
                          className={`feedback-btn ${feedback[index] === 'down' ? 'active' : ''}`}
                          onClick={() => handleFeedback(index, 'down', msg.content)}
                          title="Poor response"
                          disabled={feedback[index]}
                        >
                          👎
                        </button>
                      </div>
                    )}
                  </>
                ) : (
                  <p>{msg.content}</p>
                )}
              </div>
            ))}
            {loading && !history.some(m => m.streaming) && (
              <div className="loading-indicator">
                <span className="spinner"></span>
                <span>Thinking...</span>
              </div>
            )}
          </div>
        )}

        {/* Centered pill input */}
        <div className={`input-container ${hasMessages ? 'bottom' : 'centered'}`}>
          {/* Welcome message - only when no messages */}
          {!hasMessages && (
            <h1 className="welcome-message">Ready when you are.</h1>
          )}
          <div className="pill-input">
            <button
              className="attach-btn"
              onClick={() => fileInputRef.current?.click()}
              disabled={isUploading}
              title="Upload document"
            >
              {isUploading ? <span className="spinner small"></span> : '+'}
            </button>
            <input
              type="file"
              ref={fileInputRef}
              onChange={handleFileUpload}
              style={{ display: 'none' }}
              accept=".pdf,.txt,.md,.csv,.docx,.py,.js,.ts,.jsx,.tsx,.html,.css,.json,.xml,.yaml,.yml,.sh,.sql,.java,.c,.cpp,.h,.go,.rs,.rb,.php,.png,.jpg,.jpeg,.gif,.webp"
            />
            <textarea
              ref={textareaRef}
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              placeholder="Ask anything"
              rows={1}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault();
                  handleSendMessage();
                }
              }}
            />
            <button
              className="send-btn"
              onClick={handleSendMessage}
              disabled={loading || !message.trim()}
            >
              {loading ? <span className="spinner small white"></span> : '→'}
            </button>
          </div>

          {/* Minimal action links */}
          <div className="action-links">
            <button
              className={`link-btn search-files-btn ${searchDocs ? 'active' : ''}`}
              onClick={() => setSearchDocs(!searchDocs)}
              title="Search your uploaded documents"
            >
              {searchDocs ? '📁 Search files: ON' : '📁 Search files'}
            </button>
            {loading && <button className="link-btn" onClick={handleStop}>Stop</button>}
          </div>

          {/* Clickable model selector */}
          <div className="model-selector-container">
            <button
              className="model-selector-btn"
              onClick={() => setShowModelSelector(!showModelSelector)}
            >
              {model === 'auto' && routedModel ? (
                <>
                  Auto: <strong>{getModelDisplayName(routedModel.routed_model)}</strong>
                  <span className="category-tag">{routedModel.routed_category}</span>
                </>
              ) : model === 'auto' ? (
                <>Using: <strong>Auto</strong></>
              ) : (
                <>Using: <strong>{getModelDisplayName(model)}</strong></>
              )}
              <span className="dropdown-arrow">{showModelSelector ? '▲' : '▼'}</span>
            </button>

            {showModelSelector && (
              <div className="model-selector-dropdown">
                {MODEL_OPTIONS.map((opt) => (
                  <button
                    key={opt.id}
                    className={`model-option ${model === opt.id ? 'selected' : ''}`}
                    onClick={() => {
                      setModel(opt.id);
                      setShowModelSelector(false);
                      setRoutedModel(null); // Clear routed model when manually changing
                    }}
                  >
                    <span className="model-name">{opt.name}</span>
                    {opt.category !== 'auto' && <span className="model-category">{opt.category}</span>}
                  </button>
                ))}
                <Link
                  to="/models"
                  className="model-docs-link-bottom"
                >
                  View all models & pricing →
                </Link>
              </div>
            )}
          </div>
        </div>
      </div>
    );
  }

  // Standard mode - original layout
  return (
    <>
      <div className="chat-controls-bar" style={{ display: 'flex', alignItems: 'center', gap: 12, padding: 0, margin: 0 }}>
        <ChatControls
          model={model}
          setModel={setModel}
          searchWeb={searchWeb}
          setSearchWeb={setSearchWeb}
          temperature={temperature}
          setTemperature={setTemperature}
        />
        <ArchiveControls
          onSave={handleSave}
          onClear={handleClear}
          projectNames={projectNames}
        />
      </div>
      <div className="chat-container">
        <div className="chat-window" key={forceRerender} ref={chatWindowRef}>
          {history.map((msg, index) => (
            <div key={index} className={`message ${msg.role}`}>
              {msg.role === 'context' ? (
                <p><em>{msg.display_text}</em></p>
              ) : msg.role === 'assistant' ? (
                <>
                  {msg.streaming ? (
                    <pre style={{ whiteSpace: 'pre-wrap', fontFamily: 'inherit' }}>{msg.content}</pre>
                  ) : (
                    <div dangerouslySetInnerHTML={{ __html: marked.parse(msg.content) }} />
                  )}
                  {msg.content && !msg.streaming && (
                    <div className="message-actions">
                      <button
                        className="copy-btn"
                        onClick={() => handleCopy(msg.content, index)}
                        title="Copy to clipboard"
                      >
                        {copied[index] ? '✅' : '📋'}
                      </button>
                      <button
                        className={`feedback-btn ${feedback[index] === 'up' ? 'active' : ''}`}
                        onClick={() => handleFeedback(index, 'up', msg.content)}
                        title="Good response"
                        disabled={feedback[index]}
                      >
                        👍
                      </button>
                      <button
                        className={`feedback-btn ${feedback[index] === 'down' ? 'active' : ''}`}
                        onClick={() => handleFeedback(index, 'down', msg.content)}
                        title="Poor response"
                        disabled={feedback[index]}
                      >
                        👎
                      </button>
                    </div>
                  )}
                </>
              ) : (
                <p>{msg.content}</p>
              )}
            </div>
          ))}
        </div>
        <div className="chat-input">
          <textarea
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            placeholder="Type your message here..."
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                handleSendMessage();
              }
            }}
          />
          <button onClick={handleSendMessage} disabled={loading}>
            {loading ? 'Thinking...' : 'Send'}
          </button>
          {loading && <button onClick={handleStop}>Stop</button>}
        </div>
      </div>
    </>
  );
};

export default Chat; 