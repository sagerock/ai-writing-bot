import React, { useState, useEffect } from 'react';

const ChatControls = ({ model, setModel, searchWeb, setSearchWeb, temperature, setTemperature }) => {
  const [isMobileControlsOpen, setIsMobileControlsOpen] = useState(false);

  const getCreativityLabel = (temp) => {
    if (temp <= 0.3) return "Focused";
    if (temp <= 0.7) return "Balanced";
    if (temp <= 1.2) return "Creative";
    return "Wild";
  };

  const getMaxTemperature = () => {
    if (model.startsWith('claude-') || model.startsWith('command-') || model.startsWith('gemini-')) {
      return 1.0;
    }
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
          <label htmlFor="model-select">Model:</label>
          <select id="model-select" value={model} onChange={(e) => setModel(e.target.value)}>
            <optgroup label="OpenAI">
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
            <optgroup label="DeepSeek">
              <option value="deepseek-chat">DeepSeek Chat</option>
              <option value="deepseek-reasoner">DeepSeek Reasoner</option>
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