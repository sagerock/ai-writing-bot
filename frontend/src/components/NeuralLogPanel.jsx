import React from 'react';

// Model display names mapping
const MODEL_DISPLAY_NAMES = {
  'gpt-5.6-sol': 'GPT-5.6 Sol',
  'gpt-5.6-terra': 'GPT-5.6 Terra',
  'gpt-5.6-luna': 'GPT-5.6 Luna',
  'claude-fable-5': 'Claude Fable 5',
  'claude-opus-5': 'Claude Opus 5',
  'claude-sonnet-5': 'Claude Sonnet 5',
  'claude-haiku-4-5-20251001': 'Claude Haiku 4.5',
  'gemini-3.1-pro-preview': 'Gemini 3.1 Pro',
  'gemini-3.7-flash': 'Gemini 3.7 Flash',
  'gemini-3.5-flash-lite': 'Gemini 3.5 Flash-Lite',
  'sonar-pro': 'Perplexity Sonar Pro'
};

const getModelDisplayName = (model) => {
  return MODEL_DISPLAY_NAMES[model] || model;
};

const getCreativityLabel = (temp) => {
  if (temp <= 0.3) return 'Focused';
  if (temp <= 0.7) return 'Balanced';
  if (temp <= 1.2) return 'Creative';
  return 'Wild';
};

const NeuralLogPanel = ({
  currentModel,
  currentTemperature,
  searchWeb = false,
  entries = []
}) => {
  return (
    <div className="neural-log-panel">
      <div className="neural-log-header">
        <h3>Neural Log</h3>
        <span className="neural-log-subtitle">Transparency into AI decisions</span>
      </div>

      <div className="current-config">
        <div className="config-item">
          <span className="label">Active Model</span>
          <span className="value">{getModelDisplayName(currentModel)}</span>
        </div>
        <div className="config-item">
          <span className="label">Creativity</span>
          <span className="value">{getCreativityLabel(currentTemperature)}</span>
        </div>
        <div className="config-item">
          <span className="label">Web Search</span>
          <span className="value">{searchWeb ? 'Enabled' : 'Disabled'}</span>
        </div>
      </div>

      {entries.length > 0 && (
        <div className="log-entries">
          <h4>Recent Activity</h4>
          {entries.map((entry, idx) => (
            <div key={idx} className="log-entry">
              <span className="timestamp">{entry.timestamp}</span>
              <span className="action">{entry.action}</span>
              {entry.reason && <span className="reason">{entry.reason}</span>}
            </div>
          ))}
        </div>
      )}

      <div className="neural-log-footer">
        <p>
          Future: Auto-routing will show model selection decisions here.
          Memory updates will appear when Mem0 is integrated.
        </p>
      </div>
    </div>
  );
};

export default NeuralLogPanel;
