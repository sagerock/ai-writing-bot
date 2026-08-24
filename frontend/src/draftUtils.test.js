import test from 'node:test';
import assert from 'node:assert/strict';
import { applyDraftEdit, draftSections } from './draftUtils.js';

test('draftSections finds Markdown headings with stable line targets', () => {
  assert.deepEqual(draftSections('# Memo\n\n## Facts\nText\n\n## Analysis'), [
    { id: 'section:0', lineIndex: 0, level: 1, heading: 'Memo', headingLine: '# Memo' },
    { id: 'section:2', lineIndex: 2, level: 2, heading: 'Facts', headingLine: '## Facts' },
    { id: 'section:5', lineIndex: 5, level: 2, heading: 'Analysis', headingLine: '## Analysis' },
  ]);
});

test('applyDraftEdit replaces a section through the next peer heading', () => {
  const original = '# Memo\n\n## Facts\nOld facts\n\n### Detail\nOld detail\n\n## Analysis\nKeep this';
  const result = applyDraftEdit(original, 'New facts [1, p. 2].', 'section:2');
  assert.equal(result, '# Memo\n\n## Facts\n\nNew facts [1, p. 2].\n\n## Analysis\nKeep this');
});

test('applyDraftEdit supports whole, append, and selected-text targets', () => {
  assert.equal(applyDraftEdit('Old', '# New', 'whole'), '# New');
  assert.equal(applyDraftEdit('Old', 'New', 'append'), 'Old\n\nNew');
  assert.equal(
    applyDraftEdit('Before OLD after', 'new', 'selection', { start: 7, end: 10 }),
    'Before new after',
  );
});
