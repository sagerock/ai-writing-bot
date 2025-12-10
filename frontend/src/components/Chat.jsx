import React, { useState, useRef, useEffect } from 'react';
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

const Chat = ({
  auth,
  history,
  setHistory,
  projectNames,
  onSaveSuccess,
  simplifiedMode = true,
  defaultModel = 'gpt-5-mini-2025-08-07',
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
  const [isSaving, setIsSaving] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [searchDocs, setSearchDocs] = useState(false);
  const fileInputRef = useRef(null);

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

  const handleSendMessage = async () => {
    if (!message.trim() || loading) return;

    const userMessage = { role: 'user', content: message };
    const newHistory = [...history, userMessage];
    setHistory(newHistory);
    setMessage('');
    setLoading(true);

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
            setHistory(prev => {
              const updated = prev.map(msg => msg.streaming ? { ...msg, content: assistantResponse, streaming: false } : msg);
              console.log('After stream end:', updated[updated.length - 1]);
              return updated;
            });
            setLoading(false);
            setForceRerender(f => f + 1);
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
                setHistory(prev => prev.map(msg => msg.streaming ? { ...msg, content: assistantResponse, streaming: false } : msg));
                setLoading(false);
                setForceRerender(f => f + 1);
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
                const token = JSON.parse(dataString);
                
                assistantResponse += token;
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

  const handleClear = () => {
    if (window.confirm('Are you sure you want to clear the conversation?')) {
        setHistory([]);
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

  const handleSimplifiedSave = async () => {
    if (history.length === 0) {
      alert("Cannot save an empty chat.");
      return;
    }
    setIsSaving(true);
    try {
      const token = await auth.currentUser.getIdToken();
      const timestamp = new Date().toISOString().slice(0, 16).replace('T', ' ');
      await fetch(`${API_URL}/archive`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
          history: history,
          model: model,
          archive_name: `Chat ${timestamp}`,
          project_name: 'General',
        }),
      });
      alert('Chat saved!');
      if (onSaveSuccess) {
        onSaveSuccess();
      }
    } catch (error) {
      console.error("Error saving chat:", error);
      alert('Failed to save chat.');
    } finally {
      setIsSaving(false);
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
        {/* Neural Log Panel - only when toggled */}
        {showNeuralLog && (
          <NeuralLogPanel
            currentModel={model}
            currentTemperature={temperature}
            searchWeb={searchWeb}
          />
        )}

        {/* Empty state - centered welcome */}
        {!hasMessages && (
          <div className="welcome-container">
            <h1 className="welcome-message">Ready when you are.</h1>
          </div>
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
                      <button
                        className="copy-btn"
                        onClick={() => handleCopy(msg.content, index)}
                        title="Copy to clipboard"
                      >
                        {copied[index] ? '✅' : '📋'}
                      </button>
                    )}
                  </>
                ) : (
                  <p>{msg.content}</p>
                )}
              </div>
            ))}
          </div>
        )}

        {/* Centered pill input */}
        <div className={`input-container ${hasMessages ? 'bottom' : 'centered'}`}>
          <div className="pill-input">
            <button
              className="attach-btn"
              onClick={() => fileInputRef.current?.click()}
              disabled={isUploading}
              title="Upload document"
            >
              {isUploading ? '...' : '+'}
            </button>
            <input
              type="file"
              ref={fileInputRef}
              onChange={handleFileUpload}
              style={{ display: 'none' }}
              accept=".pdf,.txt,.md"
            />
            <label className="search-docs-toggle" title="Search your documents">
              <input
                type="checkbox"
                checked={searchDocs}
                onChange={() => setSearchDocs(!searchDocs)}
              />
              <span>Search files</span>
            </label>
            <textarea
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
              {loading ? '...' : '→'}
            </button>
          </div>

          {/* Minimal action links */}
          <div className="action-links">
            {loading && <button className="link-btn" onClick={handleStop}>Stop</button>}
            <button className="link-btn" onClick={handleSimplifiedSave} disabled={isSaving || history.length === 0}>
              {isSaving ? 'Saving...' : 'Save'}
            </button>
            {history.length > 0 && (
              <button className="link-btn" onClick={handleClear}>Clear</button>
            )}
            <button
              className={`link-btn ${showNeuralLog ? 'active' : ''}`}
              onClick={() => setShowNeuralLog(!showNeuralLog)}
            >
              {showNeuralLog ? 'Hide Log' : 'Neural Log'}
            </button>
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
                    <button
                      className="copy-btn"
                      onClick={() => handleCopy(msg.content, index)}
                      title="Copy to clipboard"
                    >
                      {copied[index] ? '✅' : '📋'}
                    </button>
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