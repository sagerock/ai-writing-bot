import DOMPurify from 'dompurify';
import { marked } from 'marked';

marked.setOptions({
  gfm: true,
  breaks: true,
});

export function renderMarkdown(markdown = '') {
  return DOMPurify.sanitize(marked.parse(markdown), {
    USE_PROFILES: { html: true },
  });
}
