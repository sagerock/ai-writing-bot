import React from 'react';

// Model display names mapping
const MODEL_DISPLAY_NAMES = {
  'gpt-5-nano-2025-08-07': 'GPT-5 Nano',
  'gpt-5-mini-2025-08-07': 'GPT-5 Mini',
  'gpt-5.2-2025-12-11': 'GPT-5.2',
  'gpt-5.2-pro-2025-12-11': 'GPT-5.2 Pro',
  'gpt-5.2-codex-2025-12-11': 'GPT-5.2 Codex',
  'claude-opus-4-6': 'Claude Opus 4.6',
  'claude-sonnet-4-6': 'Claude Sonnet 4.6',
  'claude-haiku-4-5-20251001': 'Claude Haiku 4.5',
  'gemini-3.1-pro-preview': 'Gemini 3.1 Pro',
  'gemini-3-pro-preview': 'Gemini 3 Pro',
  'gemini-3-flash-preview': 'Gemini 3 Flash',
  'gemini-2.5-pro': 'Gemini 2.5 Pro',
  'gemini-2.5-flash': 'Gemini 2.5 Flash',
  'gemini-2.5-flash-lite': 'Gemini 2.5 Flash-Lite',
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
