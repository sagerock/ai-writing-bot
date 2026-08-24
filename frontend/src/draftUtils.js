export function draftSections(markdown = '') {
  const lines = markdown.split('\n');
  const sections = [];
  lines.forEach((line, lineIndex) => {
    const match = /^(#{1,6})\s+(.+?)\s*$/.exec(line);
    if (!match) return;
    sections.push({
      id: `section:${lineIndex}`,
      lineIndex,
      level: match[1].length,
      heading: match[2],
      headingLine: line,
    });
  });
  return sections;
}

export function applyDraftEdit(markdown, content, target, selection = null) {
  const cleanContent = content.trim();
  if (target === 'whole') return cleanContent;
  if (target === 'selection' && selection && selection.end > selection.start) {
    return `${markdown.slice(0, selection.start)}${cleanContent}${markdown.slice(selection.end)}`;
  }
  if (target?.startsWith('section:')) {
    const lineIndex = Number(target.slice('section:'.length));
    const lines = markdown.split('\n');
    const headingMatch = /^(#{1,6})\s+/.exec(lines[lineIndex] || '');
    if (headingMatch) {
      const level = headingMatch[1].length;
      let endLine = lines.length;
      for (let index = lineIndex + 1; index < lines.length; index += 1) {
        const nextHeading = /^(#{1,6})\s+/.exec(lines[index]);
        if (nextHeading && nextHeading[1].length <= level) {
          endLine = index;
          break;
        }
      }
      const replacement = /^#{1,6}\s+/.test(cleanContent)
        ? cleanContent
        : `${lines[lineIndex]}\n\n${cleanContent}`;
      const spacedReplacement = endLine < lines.length ? `${replacement}\n` : replacement;
      return [...lines.slice(0, lineIndex), spacedReplacement, ...lines.slice(endLine)]
        .join('\n')
        .replace(/\n{3,}/g, '\n\n');
    }
  }
  return [markdown.trimEnd(), cleanContent].filter(Boolean).join('\n\n');
}
