const WORD_PATTERN = /[\p{L}\p{N}]+(?:['’][\p{L}\p{N}]+)*/gu;

const STOP_WORDS = new Set([
  'about', 'after', 'again', 'against', 'also', 'because', 'before', 'being',
  'between', 'both', 'could', 'does', 'from', 'have', 'into', 'more', 'most',
  'other', 'over', 'same', 'should', 'such', 'than', 'that', 'their', 'there',
  'these', 'they', 'this', 'those', 'through', 'under', 'very', 'were', 'what',
  'when', 'where', 'which', 'while', 'will', 'with', 'would', 'your',
]);

const normalizedWord = (word) => word.toLocaleLowerCase().replaceAll('’', "'");

const wordsWithOffsets = (text) => Array.from((text || '').matchAll(WORD_PATTERN), (match) => ({
  word: normalizedWord(match[0]),
  start: match.index,
  end: match.index + match[0].length,
}));

const exactTokenMatch = (text, excerpt) => {
  const sourceWords = wordsWithOffsets(text);
  const excerptWords = wordsWithOffsets(excerpt);
  if (!sourceWords.length || !excerptWords.length) return null;
  const needle = excerptWords.map(({ word }) => word);
  for (let index = 0; index <= sourceWords.length - needle.length; index += 1) {
    if (needle.every((word, offset) => sourceWords[index + offset].word === word)) {
      return {
        start: sourceWords[index].start,
        end: sourceWords[index + needle.length - 1].end,
        exact: true,
      };
    }
  }
  return null;
};

const candidatePassages = (text) => {
  const passages = [];
  const boundary = /[^.!?\n]+(?:[.!?]+|(?=\n|$))/g;
  for (const match of text.matchAll(boundary)) {
    const value = match[0].trim();
    if (!value) continue;
    const leading = match[0].indexOf(value);
    passages.push({ start: match.index + leading, end: match.index + leading + value.length });
  }
  return passages;
};

const significantWords = (text) => new Set(
  wordsWithOffsets(text)
    .map(({ word }) => word)
    .filter((word) => word.length >= 4 && !STOP_WORDS.has(word)),
);

const closestClaimMatch = (text, claim) => {
  const claimWords = significantWords(claim);
  if (claimWords.size < 2) return null;
  const passages = candidatePassages(text);
  let best = null;
  for (let startIndex = 0; startIndex < passages.length; startIndex += 1) {
    for (let length = 1; length <= 3 && startIndex + length <= passages.length; length += 1) {
      const start = passages[startIndex].start;
      const end = passages[startIndex + length - 1].end;
      const passageWords = significantWords(text.slice(start, end));
      const matches = [...claimWords].filter((word) => passageWords.has(word)).length;
      const coverage = matches / claimWords.size;
      const precision = matches / Math.max(1, passageWords.size);
      const score = (coverage * 0.75) + (precision * 0.25);
      if (!best || score > best.score) best = { start, end, matches, coverage, score };
    }
  }
  const minimumMatches = claimWords.size <= 4 ? 2 : 3;
  if (!best || best.matches < minimumMatches || best.coverage < 0.35) return null;
  return { start: best.start, end: best.end, exact: false };
};

export function findSourceHighlight(text, citation = {}) {
  if (!text) return null;
  return exactTokenMatch(text, citation.evidence) || closestClaimMatch(text, citation.claim);
}

export function claimBeforeCitation(content, offset) {
  if (!content || !Number.isInteger(offset)) return '';
  const prefix = content.slice(0, offset).trimEnd();
  const paragraph = prefix.split(/\n\s*\n/).at(-1) || '';
  const sentence = paragraph.split(/(?<=[.!?])\s+/).at(-1) || '';
  return sentence
    .replace(/^\s*(?:#{1,6}\s+|[-*+]\s+|\d+[.)]\s+)/, '')
    .replace(/\[[^\]]+\]/g, '')
    .trim();
}

export function stripEvidenceLocators(content) {
  return (content || '').replace(
    /\s*<!--\s*evidence\s+\d+\s*:\s*.*?(?:\s*-->|$)/gis,
    '',
  );
}
