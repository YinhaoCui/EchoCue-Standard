// In-page replacements for every popup WebView2 would open as its own window.
//
// A native <select> list, color picker, title tooltip, right-click menu or
// autofill list belongs to the msedgewebview2 process. Windows only lets a
// process hide its OWN windows from screen capture, so those popups would show
// outside the app's visual styling. Drawing them as page
// elements keeps them inside the main window, which is hidden.
//
// The <select> and <input type=color> elements stay in place, so their layout,
// value and 'change'/'input' events are what app.js already expects.
(() => {
 'use strict';
 const doc = document;
 let open = null;          // {pop, owner, close}
 let tip = null, tipFor = null, tipTimer = 0;

 const reshape = () => { if (typeof scheduleShape === 'function') scheduleShape(); };

 function closePopup(focusOwner) {
  if (!open) return;
  const {pop, owner} = open;
  open = null;
  pop.remove();
  owner.removeAttribute('aria-expanded');
  if (focusOwner) owner.focus({preventScroll: true});
  reshape();
 }

 // Place a popup under (or above) its owner, inside the window.
 function place(pop, owner) {
  const r = owner.getBoundingClientRect(), gap = 4, pad = 8;
  pop.style.minWidth = Math.max(r.width, 120) + 'px';
  pop.style.maxHeight = '';
  const h = pop.offsetHeight, w = pop.offsetWidth;
  const below = innerHeight - r.bottom - gap - pad, above = r.top - gap - pad;
  let top;
  if (h <= below || below >= above) { top = r.bottom + gap; pop.style.maxHeight = Math.max(80, below) + 'px'; }
  else { const room = Math.max(80, above); pop.style.maxHeight = room + 'px'; top = r.top - gap - Math.min(h, room); }
  pop.style.top = Math.max(pad, top) + 'px';
  pop.style.left = Math.max(pad, Math.min(r.left, innerWidth - w - pad)) + 'px';
 }

 function showPopup(owner, pop, onKey) {
  closePopup(false);
  hideTip();
  pop.classList.add('menu', 'popup');
  pop.style.position = 'fixed';
  pop.style.right = 'auto';
  doc.body.appendChild(pop);
  place(pop, owner);
  owner.setAttribute('aria-expanded', 'true');
  open = {pop, owner, onKey};
  reshape();
 }

 // ---- <select> -------------------------------------------------------
 function fire(el, ...types) { for (const type of types) el.dispatchEvent(new Event(type, {bubbles: true})); }

 function pickOption(select, index) {
  if (index < 0 || index >= select.options.length || select.options[index].disabled) return;
  if (select.selectedIndex !== index) { select.selectedIndex = index; fire(select, 'input', 'change'); }
 }

 function openSelect(select) {
  if (select.disabled) return;
  select.focus({preventScroll: true});
  const pop = doc.createElement('div');
  pop.setAttribute('role', 'listbox');
  pop.className = 'select-list';
  [...select.options].forEach((option, index) => {
   const item = doc.createElement('button');
   item.type = 'button';
   item.setAttribute('role', 'option');
   item.textContent = option.textContent;
   item.dataset.index = index;
   item.disabled = option.disabled;
   if (index === select.selectedIndex) { item.classList.add('selected'); item.setAttribute('aria-selected', 'true'); }
   item.addEventListener('click', () => { closePopup(true); pickOption(select, index); });
   pop.appendChild(item);
  });
  showPopup(select, pop, event => {
   const items = [...pop.querySelectorAll('button:not(:disabled)')];
   const at = items.indexOf(doc.activeElement);
   if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
    const next = items[Math.max(0, Math.min(items.length - 1, at + (event.key === 'ArrowDown' ? 1 : -1)))];
    next?.focus();
    return true;
   }
   if (event.key === 'Home' || event.key === 'End') { items[event.key === 'Home' ? 0 : items.length - 1]?.focus(); return true; }
   return false;
  });
  (pop.querySelector('.selected') || pop.querySelector('button:not(:disabled)'))?.focus({preventScroll: true});
  pop.querySelector('.selected')?.scrollIntoView({block: 'nearest'});
 }

 // Chromium opens the native list on mousedown; stop it there.
 doc.addEventListener('mousedown', event => {
  const select = event.target.closest?.('select');
  if (!select || event.button !== 0) return;
  event.preventDefault();
  if (open && open.owner === select) closePopup(true);
  else openSelect(select);
 }, true);

 // Keys that open the native list. Plain arrows change the value in place
 // on Windows without opening anything, so they are left alone.
 doc.addEventListener('keydown', event => {
  const el = event.target;
  if (el instanceof HTMLSelectElement && !open) {
   const opens = event.key === ' ' || event.key === 'Enter' || event.key === 'F4' ||
    (event.altKey && (event.key === 'ArrowDown' || event.key === 'ArrowUp'));
   if (opens) { event.preventDefault(); openSelect(el); }
   return;
  }
  if (!open) return;
  if (event.key === 'Escape') { event.preventDefault(); event.stopPropagation(); closePopup(true); return; }
  if (event.key === 'Tab') { closePopup(false); return; }
  if (open.onKey?.(event)) event.preventDefault();
 }, true);

 // ---- <input type=color> ---------------------------------------------
 const SWATCHES = [
  '#ffffff', '#e6e6e6', '#b3b3b3', '#7a7a7a', '#3d3d3d', '#000000',
  '#ffd6d6', '#ff8a80', '#e53935', '#b71c1c', '#ffe0b2', '#ffb74d',
  '#fb8c00', '#fff59d', '#fdd835', '#c5e1a5', '#7cb342', '#33691e',
  '#b2ebf2', '#26c6da', '#00838f', '#bbdefb', '#42a5f5', '#1565c0',
  '#213953', '#0d1b2a', '#d1c4e9', '#7e57c2', '#4527a0', '#f8bbd0',
 ];

 function setColor(input, value) {
  if (!/^#[0-9a-f]{6}$/i.test(value)) return false;
  value = value.toLowerCase();
  if (input.value !== value) { input.value = value; fire(input, 'input', 'change'); }
  return true;
 }

 function openColor(input) {
  const pop = doc.createElement('div');
  pop.className = 'color-list';
  pop.setAttribute('role', 'dialog');
  pop.setAttribute('aria-label', input.getAttribute('aria-label') || 'Color');
  const grid = doc.createElement('div');
  grid.className = 'swatches';
  for (const value of SWATCHES) {
   const swatch = doc.createElement('button');
   swatch.type = 'button';
   swatch.className = 'swatch' + (value === input.value.toLowerCase() ? ' selected' : '');
   swatch.style.background = value;
   swatch.setAttribute('aria-label', value);
   swatch.dataset.tip = value;
   swatch.addEventListener('click', () => { setColor(input, value); closePopup(true); });
   grid.appendChild(swatch);
  }
  const hex = doc.createElement('input');
  hex.className = 'hex';
  hex.value = input.value;
  hex.maxLength = 7;
  hex.spellcheck = false;
  hex.autocomplete = 'off';
  hex.setAttribute('aria-label', 'Hex color');
  hex.addEventListener('input', () => setColor(input, hex.value.trim()));
  hex.addEventListener('keydown', event => { if (event.key === 'Enter') { event.preventDefault(); closePopup(true); } });
  pop.append(grid, hex);
  showPopup(input, pop, null);
  grid.querySelector('.selected, .swatch')?.focus({preventScroll: true});
 }

 // Clicking (or Enter/Space, which also fire click) would open the native picker.
 doc.addEventListener('click', event => {
  const input = event.target.closest?.('input[type=color]');
  if (!input) return;
  event.preventDefault();
  if (open && open.owner === input) closePopup(true);
  else openColor(input);
 }, true);

 // Close on a press outside the popup and its owner.
 doc.addEventListener('pointerdown', event => {
  if (!open) return;
  if (open.pop.contains(event.target)) return;
  const owner = open.owner;
  if (owner.contains(event.target) || owner.closest('label')?.contains(event.target)) return;
  closePopup(false);
 }, true);
 addEventListener('blur', () => closePopup(false));
 addEventListener('resize', () => closePopup(false));
 doc.addEventListener('scroll', event => { if (open && !open.pop.contains(event.target)) closePopup(false); }, true);

 // ---- tooltips (title="...") -------------------------------------------
 // Move every title into data-tip the moment it is set, before the native
 // tooltip's hover delay, and draw the tip in the page instead.
 function adopt(el) {
  if (!(el instanceof Element) || el.closest('head, svg')) return;
  const text = el.getAttribute('title');
  if (text === null) return;
  el.removeAttribute('title');
  if (text) el.dataset.tip = text; else delete el.dataset.tip;
  if (el === tipFor) { if (text) tip.textContent = text; else hideTip(); }
 }
 function adoptAll(root) {
  if (root instanceof Element && root.hasAttribute('title')) adopt(root);
  root.querySelectorAll?.('[title]').forEach(adopt);
 }
 new MutationObserver(records => {
  for (const record of records) {
   if (record.type === 'attributes') adopt(record.target);
   else record.addedNodes.forEach(adoptAll);
  }
 }).observe(doc.body, {subtree: true, childList: true, attributes: true, attributeFilter: ['title']});
 adoptAll(doc.body);

 function hideTip() {
  clearTimeout(tipTimer);
  tipFor = null;
  if (tip) tip.hidden = true;
 }
 function showTip(el) {
  if (!tip) {
   tip = doc.createElement('div');
   tip.className = 'tip';
   tip.setAttribute('role', 'tooltip');
   doc.body.appendChild(tip);
  }
  tip.textContent = el.dataset.tip;
  tip.hidden = false;
  const r = el.getBoundingClientRect(), pad = 6;
  const w = tip.offsetWidth, h = tip.offsetHeight;
  let top = r.bottom + pad;
  if (top + h > innerHeight - pad) top = r.top - pad - h;
  tip.style.top = Math.max(pad, top) + 'px';
  tip.style.left = Math.max(pad, Math.min(r.left + r.width / 2 - w / 2, innerWidth - w - pad)) + 'px';
 }
 doc.addEventListener('pointerover', event => {
  const el = event.target.closest?.('[data-tip]');
  if (el === tipFor) return;
  hideTip();
  if (!el || open) return;
  tipFor = el;
  tipTimer = setTimeout(() => { if (tipFor === el && el.isConnected) showTip(el); }, 500);
 });
 doc.addEventListener('pointerdown', hideTip, true);
 doc.addEventListener('focusout', hideTip);
 doc.addEventListener('pointerleave', hideTip);

 // ---- right-click menu and autofill ----------------------------------
 // The browser's right-click menu is another native window. Ctrl+C/Ctrl+V
 // still work everywhere.
 doc.addEventListener('contextmenu', event => event.preventDefault());

 function noAutofill(root) {
  root.querySelectorAll?.('input:not([type=range]):not([type=checkbox]):not([type=color]), textarea')
   .forEach(el => { if (!el.hasAttribute('autocomplete')) el.setAttribute('autocomplete', 'off'); });
 }
 noAutofill(doc);
 new MutationObserver(records => records.forEach(r => r.addedNodes.forEach(noAutofill)))
  .observe(doc.body, {subtree: true, childList: true});
})();
