import test from 'node:test';
import assert from 'node:assert/strict';

import {
  claimBeforeCitation,
  findSourceHighlight,
  stripEvidenceLocators,
} from './sourceHighlight.js';

test('findSourceHighlight locates an exact evidence excerpt across whitespace and punctuation', () => {
  const text = 'Background.\nSmith learned of the injury in 2022, after the examination. Later events followed.';
  const match = findSourceHighlight(text, {
    evidence: 'Smith learned of the injury in 2022 after the examination',
  });
  assert.equal(text.slice(match.start, match.end), 'Smith learned of the injury in 2022, after the examination');
  assert.equal(match.exact, true);
});

test('findSourceHighlight conservatively finds the closest passage for an older citation', () => {
  const text = 'The weather was clear. Smith discovered the latent injury during a medical examination in 2022. The complaint followed.';
  const match = findSourceHighlight(text, {
    claim: 'Smith learned about the latent injury during a 2022 medical examination',
  });
  assert.match(text.slice(match.start, match.end), /Smith discovered the latent injury/);
  assert.equal(match.exact, false);
});

test('citation helpers recover a claim and remove invisible evidence metadata', () => {
  const content = 'The claim accrued in 2022 [1, p. 4]<!-- evidence 1: the claim accrued in 2022 -->.';
  assert.equal(claimBeforeCitation(content, content.indexOf('[1')), 'The claim accrued in 2022');
  assert.equal(stripEvidenceLocators(content), 'The claim accrued in 2022 [1, p. 4].');
});
