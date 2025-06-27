import React, { useState, useRef, useEffect } from 'react';
import { marked } from 'marked';
import ChatControls from './ChatControls';
import ArchiveControls from './ArchiveControls';

const Chat = ({ auth, history, setHistory, projectNames, onSaveSuccess }) => {
  const [message, setMessage] = useState('');
  const [loading, setLoading] = useState(false);
  const [model, setModel] = useState('chatgpt-4o-latest');
  const [searchWeb, setSearchWeb] = useState(false);
  const abortControllerRef = useRef(null);
  const [copied, setCopied] = useState({});

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
      // Using EventSource for streaming
      const eventSource = new EventSource(`http://127.0.0.1:8000/chat_stream?token=${token}&model=${model}&search_web=${searchWeb}&history=${encodeURIComponent(JSON.stringify(newHistory))}`);
      
      let assistantResponse = '';
      setHistory(prev => [...prev, { role: 'assistant', content: '' }]);

      eventSource.onmessage = (event) => {
        if (event.data === "[DONE]") {
            eventSource.close();
            setLoading(false);
            return;
        }
        assistantResponse += event.data;
        setHistory(prev => {
          const updatedHistory = [...prev];
          updatedHistory[updatedHistory.length - 1].content = assistantResponse;
          return updatedHistory;
        });
      };

      eventSource.onerror = (err) => {
        console.error("EventSource failed:", err);
        eventSource.close();
        setLoading(false);
        setHistory(prev => [...prev, { role: 'assistant', content: 'Sorry, I encountered an error.' }]);
      };
      
      abortControllerRef.current.signal.onabort = () => {
        eventSource.close();
        setLoading(false);
      };

    } catch (error) {
      console.error("Error sending message:", error);
      if (error.name !== 'AbortError') {
        setHistory(prev => [...prev, { role: 'assistant', content: 'Sorry, I encountered an error.' }]);
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
        await fetch('http://127.0.0.1:8000/archive', {
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
      />
      <ArchiveControls 
        onSave={handleSave} 
        onClear={handleClear} 
        projectNames={projectNames} 
      />
      <div className="chat-container">
        <div className="chat-window">
          {history.map((msg, index) => (
            <div key={index} className={`message ${msg.role}`}>
              {msg.role === 'context' ? (
                <p><em>{msg.display_text}</em></p>
              ) : msg.role === 'assistant' ? (
                <>
                  <div dangerouslySetInnerHTML={{ __html: marked.parse(msg.content) }} />
                  {msg.content && (
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