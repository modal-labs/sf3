export const byId = (id) => document.getElementById(id);
export const $ = (selector, root = document) => root.querySelector(selector);
export const $$ = (selector, root = document) =>
  Array.from(root.querySelectorAll(selector));

export const setHidden = (el, hidden = true) => {
  if (el) el.classList.toggle("hidden", hidden);
};

export const show = (el) => setHidden(el, false);
export const hide = (el) => setHidden(el, true);

export const setText = (id, text) => {
  const el = byId(id);
  if (el) el.textContent = text;
};

export const isHidden = (el) => !el || el.classList.contains("hidden");
