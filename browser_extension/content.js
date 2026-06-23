/**
 * AURA Browser Bridge — content script.
 *
 * Injected into every page. Reads the DOM/ARIA accessibility tree,
 * watches for dynamic content changes via MutationObserver, and
 * surfaces structured page data (headings, tables, forms, landmarks)
 * to the background script for relay to AURA's Python backend.
 *
 * TODO: implement (Goals 11, 12)
 */

console.log("[AURA] Content script loaded on", window.location.href);
