import React, { useState, useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';

// Model documentation links
const MODEL_DOCS = {
  openai: { name: 'OpenAI', url: 'https://developers.openai.com/api/docs/models' },
  anthropic: { name: 'Anthropic', url: 'https://platform.claude.com/docs/en/about-claude/models/overview' },
  google: { name: 'Google', url: 'https://ai.google.dev/gemini-api/docs/models' },
  perplexity: { name: 'Perplexity', url: 'https://docs.perplexity.ai/docs/sonar/models' },
};

const ChatControls = ({ model, setModel, modelOptions, searchWeb, setSearchWeb, temperature, setTemperature }) => {
  const [isMobileControlsOpen, setIsMobileControlsOpen] = useState(false);
  const [showModelDocs, setShowModelDocs] = useState(false);

  const getCreativityLabel = (temp) => {
    if (temp <= 0.3) return "Focused";
    if (temp <= 0.7) return "Balanced";
    if (temp <= 1.2) return "Creative";
    return "Wild";
  };

  const getMaxTemperature = useCallback(() => {
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
  }, [model]);

  const temperatureManagedByModel = model.startsWith('gpt-5.6') || model.startsWith('gemini-3.');

  const groupedModels = (modelOptions || [])
    .filter((option) => option.id !== 'auto')
    .reduce((groups, option) => {
      const provider = option.provider || 'Other';
      if (!groups[provider]) groups[provider] = [];
      groups[provider].push(option);
      return groups;
    }, {});

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
  }, [getMaxTemperature, temperature, setTemperature]);

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
          <div className="w-full">
            <label htmlFor="creativity-slider" className="block text-sm font-medium text-gray-700 dark:text-gray-300">
              Creativity:{' '}
              <span className="font-bold">
                {temperatureManagedByModel ? 'Model-managed' : getCreativityLabel(temperature)}
              </span>
              {!temperatureManagedByModel && ` (${temperature.toFixed(1)})`}
            </label>
            <input
              id="creativity-slider"
              type="range"
              min="0"
              max={getMaxTemperature()}
              step="0.1"
              value={temperature}
              onChange={handleTemperatureChange}
              disabled={temperatureManagedByModel}
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
