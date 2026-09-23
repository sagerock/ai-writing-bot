import React, { useState } from 'react';
import { Link } from 'react-router-dom';

// Model documentation links
const MODEL_DOCS = {
  openai: { name: 'OpenAI', url: 'https://developers.openai.com/api/docs/models' },
  anthropic: { name: 'Anthropic', url: 'https://platform.claude.com/docs/en/about-claude/models/overview' },
};

// Every current model manages its own sampling, so the creativity slider is gone.
const ChatControls = ({ model, setModel, modelOptions, searchWeb, setSearchWeb }) => {
  const [isMobileControlsOpen, setIsMobileControlsOpen] = useState(false);
  const [showModelDocs, setShowModelDocs] = useState(false);

  const groupedModels = (modelOptions || [])
    .filter((option) => option.id !== 'auto')
    .reduce((groups, option) => {
      const provider = option.provider || 'Other';
      if (!groups[provider]) groups[provider] = [];
      groups[provider].push(option);
      return groups;
    }, {});

  return (
    <div className="chat-controls-wrapper mobile-accordion">
       <button className="mobile-accordion-header" onClick={() => setIsMobileControlsOpen(!isMobileControlsOpen)}>
          <h2>Chat Settings</h2>
          <span>{isMobileControlsOpen ? '−' : '+'}</span>
      </button>
      <div className={`chat-controls bg-white dark:bg-gray-800 p-4 border-t border-gray-200 dark:border-gray-700 mobile-accordion-panel ${isMobileControlsOpen ? 'is-open' : ''}`}>
        <div className="control-group">
          <div className="model-label-row">
            <label htmlFor="model-select">Model:</label>
            <div className="model-docs-wrapper">
              <button
                type="button"
                className="model-info-btn"
                onClick={() => setShowModelDocs(!showModelDocs)}
                title="View latest models from providers"
              >
                ℹ️
              </button>
              {showModelDocs && (
                <div className="model-docs-dropdown">
                  <div className="model-docs-header">Model Resources</div>
                  <Link to="/models" className="model-docs-link model-pricing-link">
                    View All Models & Pricing →
                  </Link>
                  <div className="model-docs-divider"></div>
                  {Object.entries(MODEL_DOCS).map(([key, { name, url }]) => (
                    <a
                      key={key}
                      href={url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="model-docs-link"
                    >
                      {name} Docs →
                    </a>
                  ))}
                </div>
              )}
            </div>
          </div>
          <select id="model-select" value={model} onChange={(e) => setModel(e.target.value)}>
            <option value="auto">Auto (Smart Routing)</option>
            {Object.entries(groupedModels).map(([provider, options]) => (
              <optgroup key={provider} label={provider}>
                {options.map((option) => (
                  <option key={option.id} value={option.id}>{option.name}</option>
                ))}
              </optgroup>
            ))}
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
    </div>
  );
};

export default ChatControls;
