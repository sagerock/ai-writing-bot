import React from 'react';

const ChatControls = ({ model, setModel, searchWeb, setSearchWeb }) => {
  return (
    <div className="chat-controls">
      <div className="control-group">
        <label htmlFor="model-select">Model:</label>
        <select id="model-select" value={model} onChange={(e) => setModel(e.target.value)}>
          <optgroup label="OpenAI">
            <option value="chatgpt-4o-latest">ChatGPT 4o (Latest)</option>
            <option value="gpt-4.1-2025-04-14">GPT-4.1</option>
            <option value="gpt-4.1-mini-2025-04-14">GPT-4.1 Mini</option>
            <option value="o3-2025-04-16">o3</option>
            <option value="o3-mini-2025-01-31">o3 Mini</option>
          </optgroup>
          <optgroup label="Anthropic">
            <option value="claude-opus-4-20250514">Claude Opus 4</option>
            <option value="claude-sonnet-4-20250514">Claude Sonnet 4</option>
            <option value="claude-3-7-sonnet-20250219">Claude Sonnet 3.7</option>
            <option value="claude-3-5-sonnet-20241022">Claude Sonnet 3.5</option>
            <option value="claude-3-5-haiku-20241022">Claude Haiku 3.5</option>
            <option value="claude-3-opus-20240229">Claude Opus 3</option>
          </optgroup>
          <optgroup label="Cohere">
            <option value="command-r-plus">Command R+</option>
            <option value="command-r">Command R</option>
          </optgroup>
          <optgroup label="Google">
            <option value="gemini-2.5-pro">Gemini 2.5 Pro</option>
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