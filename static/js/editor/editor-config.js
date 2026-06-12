// editor-config.js — feature flags for the gallery image editor.
//
// ADVANCED_EDITING gates the editor down to a minimal, user-friendly
// toolset. When false (the ArgoDesk default), the editor exposes only
// the basics — move, crop, transform/rotate, brush, eraser and the
// simple adjustments — and hides the advanced tooling: clone, lasso,
// wand, inpaint, remove-background, sharpen, the layer panel and the
// effects/filters menu.
//
// This is intentionally a single reversible switch: flip it to `true`
// to restore the full professional editor. No editor code is deleted —
// the advanced modules stay on disk and simply aren't surfaced.
export const ADVANCED_EDITING = false;

export default { ADVANCED_EDITING };
