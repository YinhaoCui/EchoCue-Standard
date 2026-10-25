// Markdown for the Live transcript and AI answer panels.
//
// Safe by construction: every node is built with createElement / createTextNode,
// never innerHTML, so model output cannot inject markup or script. Links are shown
// as text with the address as a tooltip; the app window never navigates.
//
// Incremental: the text is cut into blocks (paragraph, list, code fence, ...) and
// a block is re-rendered only when its own source changed, so a streaming answer
// redraws just its last block instead of the whole panel.
'use strict';

const MD_LIST = /^(\s*)([-*+]|\d{1,9}[.)])\s+(.*)$/;
const MD_FENCE = /^\s*(```+|~~~+)\s*([\w+#.-]*)\s*$/;
const MD_HEADING = /^\s{0,3}(#{1,6})\s+(.*?)\s*#*\s*$/;
const MD_RULE = /^\s{0,3}([-*_])(\s*\1){2,}\s*$/;
const MD_TABLE_RULE = /^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$/;

function mdBlocks(text) {
 const blocks = [];
 let current = null, fence = null;
 const close = () => { if (current) blocks.push(current); current = null; };
 for (const line of text.replace(/\r\n?/g, '\n').split('\n')) {
  if (fence) {
   if (new RegExp('^\\s*' + fence.marker[0] + '{' + fence.marker.length + ',}\\s*$').test(line)) { fence.closed = true; blocks.push(fence); fence = null; }
   else fence.lines.push(line);
   continue;
  }
  const open = line.match(MD_FENCE);
  if (open) { close(); fence = {type: 'code', marker: open[1], lang: open[2], lines: [], closed: false}; continue; }
  if (!line.trim()) { close(); continue; }
  if (MD_HEADING.test(line) || MD_RULE.test(line)) { close(); blocks.push({type: MD_HEADING.test(line) ? 'heading' : 'rule', lines: [line]}); continue; }
  const kind = MD_LIST.test(line) ? 'list' : /^\s*>/.test(line) ? 'quote' : /^\s*\|/.test(line) ? 'table' : 'text';
  // A plain line right after a list item or quote continues it (lazy continuation).
  if (current && (current.type === kind || (kind === 'text' && (current.type === 'list' || current.type === 'quote')))) current.lines.push(line);
  else { close(); current = {type: kind, lines: [line]}; }
 }
 close();
 if (fence) blocks.push(fence);  // still streaming: show what has arrived as code
 for (const block of blocks) block.key = block.type + '\u0000' + (block.lang || '') + '\u0000' + block.closed + '\u0000' + block.lines.join('\n');
 return blocks;
}

const MD_INLINE = new RegExp([
 '\\\\([\\\\`*_{}\\[\\]()#+\\-.!|~>])',                 // 1 escaped character
 '(`+)([^`]|[^`][\\s\\S]*?[^`])\\2(?!`)',                // 2,3 code span
 '\\*\\*(?=\\S)([\\s\\S]*?\\S)\\*\\*',                    // 4 bold
 '__(?=\\S)([\\s\\S]*?\\S)__(?!\\w)',                     // 5 bold
 '~~(?=\\S)([\\s\\S]*?\\S)~~',                            // 6 strikethrough
 '\\*(?=[^\\s*])([\\s\\S]*?[^\\s*])\\*(?!\\*)',           // 7 italic
 '(?<![\\w_])_(?=[^\\s_])([\\s\\S]*?[^\\s_])_(?![\\w_])', // 8 italic, not inside snake_case
 '\\[([^\\]\\n]+)\\]\\(\\s*([^)\\s]+)(?:\\s+"[^"]*")?\\s*\\)', // 9,10 link
].join('|'), 'g');

function mdInline(text, parent) {
 let at = 0;
 MD_INLINE.lastIndex = 0;
 for (let m; (m = MD_INLINE.exec(text));) {
  if (m.index > at) parent.appendChild(document.createTextNode(text.slice(at, m.index)));
  at = MD_INLINE.lastIndex;
  let el;
  if (m[1] !== undefined) { parent.appendChild(document.createTextNode(m[1])); continue; }
  if (m[3] !== undefined) { el = document.createElement('code'); el.textContent = m[3].replace(/^ (.*) $/, '$1'); parent.appendChild(el); continue; }
  if (m[4] !== undefined || m[5] !== undefined) { el = document.createElement('strong'); mdInline(m[4] ?? m[5], el); }
  else if (m[6] !== undefined) { el = document.createElement('del'); mdInline(m[6], el); }
  else if (m[7] !== undefined || m[8] !== undefined) { el = document.createElement('em'); mdInline(m[7] ?? m[8], el); }
  else { el = document.createElement('span'); el.className = 'md-link'; el.title = m[10]; mdInline(m[9], el); }
  parent.appendChild(el);
  MD_INLINE.lastIndex = at;  // nested calls reset the shared pattern
 }
 if (at < text.length) parent.appendChild(document.createTextNode(text.slice(at)));
}

function mdLines(lines, parent) {
 lines.forEach((line, i) => { if (i) parent.appendChild(document.createElement('br')); mdInline(line.replace(/\s+$/, ''), parent); });
}

function mdList(lines) {
 // Nesting follows indentation; a deeper item opens a list inside the previous item.
 const root = {indent: -1, list: null, item: null}, stack = [root];
 for (const line of lines) {
  const m = line.match(MD_LIST);
  if (!m) {  // continuation of the current item
   const item = stack[stack.length - 1].item;
   if (item) { item.appendChild(document.createElement('br')); mdInline(line.trim(), item); }
   continue;
  }
  const indent = m[1].replace(/\t/g, '    ').length, ordered = /\d/.test(m[2]);
  while (stack.length > 2 && indent < stack[stack.length - 1].indent) stack.pop();  // never drop the outer list
  let level = stack[stack.length - 1];
  if (indent > level.indent && (level === root || level.item)) {
   const list = document.createElement(ordered ? 'ol' : 'ul');
   if (ordered && parseInt(m[2], 10) !== 1) list.start = parseInt(m[2], 10);
   (level.item || null)?.appendChild(list);
   level = {indent, list, item: null}; stack.push(level);
   if (!root.list) root.list = list;
  }
  const item = document.createElement('li');
  const task = m[3].match(/^\[([ xX])\]\s+(.*)$/);
  if (task) { item.className = 'md-task'; item.appendChild(document.createTextNode(task[1] === ' ' ? '☐ ' : '☑ ')); mdInline(task[2], item); }
  else mdInline(m[3], item);
  level.list.appendChild(item); level.item = item;
 }
 return root.list;
}

function mdCells(line) {
 return line.trim().replace(/^\|/, '').replace(/\|$/, '').split(/(?<!\\)\|/).map(cell => cell.trim().replace(/\\\|/g, '|'));
}

function mdTable(lines) {
 if (lines.length < 2 || !MD_TABLE_RULE.test(lines[1])) return null;
 const table = document.createElement('table'), head = table.createTHead().insertRow(), body = table.createTBody();
 const align = mdCells(lines[1]).map(c => c.startsWith(':') && c.endsWith(':') ? 'center' : c.endsWith(':') ? 'right' : '');
 mdCells(lines[0]).forEach((text, i) => { const th = document.createElement('th'); th.style.textAlign = align[i] || ''; mdInline(text, th); head.appendChild(th); });
 for (const line of lines.slice(2)) {
  const row = body.insertRow();
  mdCells(line).forEach((text, i) => { const td = row.insertCell(); td.style.textAlign = align[i] || ''; mdInline(text, td); });
 }
 const wrap = document.createElement('div'); wrap.className = 'md-table'; wrap.appendChild(table);
 return wrap;
}

function mdRender(block) {
 let el;
 switch (block.type) {
  case 'code': {
   el = document.createElement('pre'); el.className = 'md-code';
   const code = el.appendChild(document.createElement('code'));
   if (block.lang) code.dataset.lang = block.lang;
   code.textContent = block.lines.join('\n');
   return el;
  }
  case 'heading': {
   const [, hashes, text] = block.lines[0].match(MD_HEADING);
   el = document.createElement('h' + Math.min(6, hashes.length + 2)); el.className = 'md-h md-h' + hashes.length;  // page h1/h2 stay the app's own
   mdInline(text, el); return el;
  }
  case 'rule': return document.createElement('hr');
  case 'quote': {
   el = document.createElement('blockquote');
   const inner = block.lines.map(line => line.replace(/^\s*>\s?/, '')).join('\n');
   for (const child of mdBlocks(inner)) el.appendChild(mdRender(child));
   return el;
  }
  case 'list': return mdList(block.lines);
  case 'table': { const table = mdTable(block.lines); if (table) return table; }  // not a table: a paragraph
  // falls through
  default: el = document.createElement('p'); mdLines(block.lines, el); return el;
 }
}

function renderMarkdown(el, text) {
 // Rebuild only from the first block whose source changed.
 const old = el._mdBlocks || [], blocks = mdBlocks(text);
 if (!el._mdBlocks) el.textContent = '';
 let same = 0;
 while (same < old.length && same < blocks.length && old[same].key === blocks[same].key) same++;
 for (const gone of old.slice(same)) gone.node.remove();
 for (const block of blocks.slice(same)) { block.node = mdRender(block); el.appendChild(block.node); }
 for (let i = 0; i < same; i++) blocks[i].node = old[i].node;
 el._mdBlocks = blocks;
 el._mdSource = text;
}
