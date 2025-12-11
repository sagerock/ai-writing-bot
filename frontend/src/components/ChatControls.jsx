import React, { useState, useEffect } from 'react';

// Model documentation links
const MODEL_DOCS = {
  openai: { name: 'OpenAI', url: 'https://platform.openai.com/docs/models' },
  anthropic: { name: 'Anthropic', url: 'https://docs.anthropic.com/en/docs/about-claude/models/overview' },
  google: { name: 'Google', url: 'https://ai.google.dev/gemini-api/docs/models' },
  perplexity: { name: 'Perplexity', url: 'https://docs.perplexity.ai/guides/model-cards' },
};

const ChatControls = ({ model, setModel, searchWeb, setSearchWeb, temperature, setTemperature }) => {
  const [isMobileControlsOpen, setIsMobileControlsOpen] = useState(false);
  const [showModelDocs, setShowModelDocs] = useState(false);

  const getCreativityLabel = (temp) => {
    if (temp <= 0.3) return "Focused";
    if (temp <= 0.7) return "Balanced";
    if (temp <= 1.2) return "Creative";
    return "Wild";
  };

  const getMaxTemperature = () => {
    // Auto mode - default to 1.0 (will be adjusted by actual model)
    if (model === 'auto') {
      return 1.0;
    }
    // GPT-5 models only support temperature = 1
    if (model.startsWith('gpt-5')) {
      return 1.0;
    }
    // Claude, Cohere, and Gemini models max at 1.0
    if (model.startsWith('claude-') || model.startsWith('command-') || model.startsWith('gemini-')) {
      return 1.0;
    }
    // Other models (GPT-4, etc.) can go up to 1.5
    return 1.5;
  };

  const handleTemperatureChange = (e) => {
    const newTemp = parseFloat(e.target.value);
    const maxTemp = getMaxTemperature();
    setTemperature(Math.min(newTemp, maxTemp));
  };

  useEffect(() => {
    localStorage.setItem('temperature', temperature);
    const maxTemp = getMaxTemperature();
    if (temperature > maxTemp) {
      setTemperature(maxTemp);
    }
  }, [model, temperature, setTemperature]);

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
                  <div className="model-docs-header">Latest Model Docs</div>
                  {Object.entries(MODEL_DOCS).map(([key, { name, url }]) => (
                    <a
                      key={key}
                      href={url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="model-docs-link"
                    >
                      {name} →
                    </a>
                  ))}
                </div>
              )}
            </div>
          </div>
          <select id="model-select" value={model} onChange={(e) => setModel(e.target.value)}>
            <option value="auto">Auto (Smart Routing)</option>
            <optgroup label="OpenAI - GPT-5 Series">
              <option value="gpt-5-nano-2025-08-07">GPT-5 Nano (Ultra-fast)</option>
              <option value="gpt-5-mini-2025-08-07">GPT-5 Mini (Default)</option>
              <option value="gpt-5-2025-08-07">GPT-5 (Premium)</option>
              <option value="gpt-5-pro-2025-10-06">GPT-5 Pro (Advanced)</option>
              <option value="gpt-5.1-2025-11-13">GPT-5.1 (Latest)</option>
            </optgroup>
            <optgroup label="OpenAI - GPT-4.1 Series">
              <option value="gpt-4.1-nano-2025-04-14">GPT-4.1 Nano</option>
              <option value="gpt-4.1-mini-2025-04-14">GPT-4.1 Mini</option>
              <option value="gpt-4.1-2025-04-14">GPT-4.1</option>
            </optgroup>
            <optgroup label="Anthropic">
              <option value="claude-sonnet-4-5-20250929">Claude Sonnet 4.5</option>
              <option value="claude-opus-4-1-20250805">Claude Opus 4.1 (Research)</option>
            </optgroup>
            <optgroup label="Google">
              <option value="gemini-2.5-flash">Gemini Flash (Fast)</option>
              <option value="gemini-2.5-pro">Gemini 2.5 Pro (Educational)</option>
            </optgroup>
            <optgroup label="Perplexity">
              <option value="sonar-pro">Sonar Pro (Real-time Search)</option>
            </optgroup>
          </select>
        </div>
        <div className="control-group">
          <div className="w-full">
            <label htmlFor="creativity-slider" className="block text-sm font-medium text-gray-700 dark:text-gray-300">
              Creativity: <span className="font-bold">{getCreativityLabel(temperature)}</span> ({temperature.toFixed(1)})
            </label>
            <input
              id="creativity-slider"
              type="range"
              min="0"
              max={getMaxTemperature()}
              step="0.1"
              value={temperature}
              onChange={handleTemperatureChange}
              className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer dark:bg-gray-700"
            />
          </div>
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