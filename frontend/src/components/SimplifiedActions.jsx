import React from 'react';

const SimplifiedActions = ({
  onSave,
  onClear,
  onToggleNeuralLog,
  showNeuralLog,
  isSaving = false
}) => {
  return (
    <div className="simplified-actions">
      <button
        onClick={onSave}
        disabled={isSaving}
        className="action-btn save"
        title="Save Chat"
      >
        {isSaving ? 'Saving...' : 'Save'}
      </button>
      <button
        onClick={onClear}
        className="action-btn clear"
        title="Clear Memory"
      >
        Clear
      </button>
      <button
        onClick={onToggleNeuralLog}
        className={`action-btn neural ${showNeuralLog ? 'active' : ''}`}
        title="Show AI decisions"
      >
        {showNeuralLog ? 'Hide Log' : 'Neural Log'}
      </button>
    </div>
  );
};

export default SimplifiedActions;
