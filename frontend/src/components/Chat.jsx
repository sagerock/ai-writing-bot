import React, { useState, useRef, useEffect } from 'react';
import { marked } from 'marked';
import ChatControls from './ChatControls';
import ArchiveControls from './ArchiveControls';
import { API_URL } from '../apiConfig';

// Configure marked to treat single line breaks as <br> tags (GitHub-style)
marked.setOptions({
  gfm: true,
  breaks: true,
});

const Chat = ({ auth, history, setHistory, projectNames, onSaveSuccess }) => {
  const [message, setMessage] = useState('');
  const [loading, setLoading] = useState(false);
  const [model, setModel] = useState('chatgpt-4o-latest');
  const [searchWeb, setSearchWeb] = useState(false);
  const [temperature, setTemperature] = useState(0.7);
  const abortControllerRef = useRef(null);
  const [copied, setCopied] = useState({});
  const [forceRerender, setForceRerender] = useState(0);

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

              try {
                const token = JSON.parse(dataString);
                
                if (token === '[DONE]') {
                  setHistory(prev => prev.map(msg => msg.streaming ? { ...msg, content: assistantResponse, streaming: false } : msg));
                  setLoading(false);
                  setForceRerender(f => f + 1);
                  return;
                }
                
                assistantResponse += token;
                setHistory(prev => prev.map(msg => msg.streaming ? { ...msg, content: assistantResponse } : msg));

              } catch (e) {
                console.error("Failed to parse JSON from stream:", dataString, e);
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

  return (
    <>
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
      <div className="chat-container">
        <div className="chat-window" key={forceRerender}>
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