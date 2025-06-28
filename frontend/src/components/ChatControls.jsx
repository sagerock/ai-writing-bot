import React from 'react';

const ChatControls = ({ model, setModel, searchWeb, setSearchWeb }) => {
  return (
    <div className="chat-controls">
      <div className="control-group">
        <label htmlFor="model-select">Model:</label>
        <select id="model-select" value={model} onChange={(e) => setModel(e.target.value)}>
          <optgroup label="OpenAI">
            <option value="gpt-4.5-preview">GPT-4.5 Preview</option>
            <option value="gpt-4o">GPT-4o</option>
            <option value="gpt-4.1">GPT-4.1</option>
            <option value="gpt-4.1-mini">GPT-4.1 Mini</option>
            <option value="gpt-4.1-nano">GPT-4.1 Nano</option>
          </optgroup>
          <optgroup label="Anthropic">
            <option value="claude-opus-4-20250514">Claude 4 Opus</option>
            <option value="claude-3-7-sonnet-20250219">Claude 3.7 Sonnet</option>
            <option value="claude-3-5-sonnet-20241022">Claude 3.5 Sonnet</option>
            <option value="claude-3-5-haiku-20241022">Claude 3.5 Haiku</option>
            <option value="claude-3-opus-20240229">Claude 3 Opus (Legacy)</option>
          </optgroup>
          <optgroup label="Cohere">
            <option value="command-r-plus">Command R+</option>
            <option value="command-r">Command R</option>
          </optgroup>
          <optgroup label="xAI">
            <option value="grok-3-latest">Grok 3</option>
          </optgroup>
          <optgroup label="Google">
            <option value="gemini-2.5-pro">Gemini 2.5 Pro</option>
            <option value="gemini-2.5-flash">Gemini 2.5 Flash</option>
          </optgroup>
        </select>
      </div>
      <div className="control-group">
        <label>
          <input
            type="checkbox"
            checked={searchWeb}
            onChange={(e) => setSearchWeb(e.target.checked)}
          />
          Search Web
        </label>
      </div>
    </div>
  );
};

export default ChatControls; 