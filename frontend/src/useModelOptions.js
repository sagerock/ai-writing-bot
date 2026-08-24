import { useEffect, useState } from 'react';
import { API_URL } from './apiConfig';

const FALLBACK_MODELS = [
  { id: 'gpt-5.6-sol', name: 'GPT-5.6 Sol', provider: 'OpenAI' },
  { id: 'gpt-5.6-terra', name: 'GPT-5.6 Terra', provider: 'OpenAI' },
  { id: 'gpt-5.6-luna', name: 'GPT-5.6 Luna', provider: 'OpenAI' },
  { id: 'claude-fable-5', name: 'Claude Fable 5', provider: 'Anthropic' },
  { id: 'claude-opus-5', name: 'Claude Opus 5', provider: 'Anthropic' },
  { id: 'claude-sonnet-5', name: 'Claude Sonnet 5', provider: 'Anthropic' },
  { id: 'claude-haiku-4-5-20251001', name: 'Claude Haiku 4.5', provider: 'Anthropic' },
  { id: 'gemini-3.7-flash', name: 'Gemini 3.7 Flash', provider: 'Google' },
  { id: 'gemini-3.5-flash-lite', name: 'Gemini 3.5 Flash-Lite', provider: 'Google' },
  { id: 'gemini-3.1-pro-preview', name: 'Gemini 3.1 Pro', provider: 'Google' },
  { id: 'sonar-pro', name: 'Sonar Pro', provider: 'Perplexity' },
];

const INITIAL_OPTIONS = [
  { id: 'auto', name: 'Auto (Smart Routing)', provider: 'Auto' },
  ...FALLBACK_MODELS,
];

export function useModelOptions() {
  const [options, setOptions] = useState(INITIAL_OPTIONS);

  useEffect(() => {
    const controller = new AbortController();

    fetch(`${API_URL}/models`, { signal: controller.signal })
      .then((response) => {
        if (!response.ok) throw new Error('Model catalog request failed');
        return response.json();
      })
      .then((data) => {
        if (Array.isArray(data.models) && data.models.length > 0) {
          setOptions([
            INITIAL_OPTIONS[0],
            ...data.models.map((model) => ({
              id: model.id,
              name: model.name,
              provider: model.provider,
            })),
          ]);
        }
      })
      .catch((error) => {
        if (error.name !== 'AbortError') {
          console.warn('Using bundled model catalog:', error.message);
        }
      });

    return () => controller.abort();
  }, []);

  return options;
}
