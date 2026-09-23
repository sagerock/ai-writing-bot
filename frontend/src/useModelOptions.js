import { useEffect, useState } from 'react';
import { API_URL } from './apiConfig';

const FALLBACK_MODELS = [
  { id: 'claude-sonnet-5', name: 'Claude Sonnet 5', provider: 'Anthropic' },
  { id: 'claude-opus-5-5', name: 'Claude Opus 5.5', provider: 'Anthropic' },
  { id: 'gpt-6-luna', name: 'GPT-6 Luna', provider: 'OpenAI' },
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
