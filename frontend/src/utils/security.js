import DOMPurifyModule from 'dompurify';
import { marked } from 'marked';

// Configure marked defaults
marked.setOptions({
  gfm: true,
  breaks: true,
});

/**
 * Obtain the appropriate DOMPurify instance (browser window or Node environment).
 */
export function getDOMPurify() {
  if (typeof window !== 'undefined') {
    if (typeof DOMPurifyModule.sanitize === 'function') {
      return DOMPurifyModule;
    }
    return DOMPurifyModule(window);
  }
  if (typeof globalThis.window !== 'undefined') {
    return DOMPurifyModule(globalThis.window);
  }
  return DOMPurifyModule;
}

/**
 * Check if the HTML content genuinely contains or requires scripts.
 */
export function requiresScript(content) {
  if (!content) return false;
  return /<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>/i.test(content) ||
         /\bon[a-z]+\s*=/i.test(content);
}

/**
 * Compute the least-privilege iframe sandbox attribute value.
 * - Static HTML with no JavaScript: "" (the most restrictive sandbox possible)
 * - Only use "allow-scripts" when JavaScript is genuinely required.
 * - NEVER add "allow-same-origin".
 * - NEVER add "allow-top-navigation", "allow-popups", "allow-forms", etc.
 */
export function getIframeSandbox(content) {
  return requiresScript(content) ? "allow-scripts" : "";
}

/**
 * Generates the restrictive Content Security Policy string.
 * @param {boolean} allowScripts
 */
export function getCSPDirectives(allowScripts = false) {
  const scriptPolicy = allowScripts ? "script-src 'unsafe-inline'" : "script-src 'none'";
  return [
    "default-src 'none'",
    "style-src 'unsafe-inline'",
    "img-src data:",
    "font-src data:",
    "connect-src 'none'",
    "form-action 'none'",
    "base-uri 'none'",
    scriptPolicy,
  ].join("; ") + ";";
}

/**
 * Prepares HTML content for rendering inside a sandboxed iframe
 * by ensuring a restrictive Content-Security-Policy meta tag is in the <head>.
 */
export function prepareHtmlArtifact(rawHtml) {
  if (!rawHtml) return "";
  const needsScript = requiresScript(rawHtml);
  const cspString = getCSPDirectives(needsScript);
  const metaTag = `<meta http-equiv="Content-Security-Policy" content="${cspString}">`;

  // Replace existing CSP if present to ensure strictness
  if (/<meta[^>]*http-equiv=["']Content-Security-Policy["'][^>]*>/i.test(rawHtml)) {
    return rawHtml.replace(/<meta[^>]*http-equiv=["']Content-Security-Policy["'][^>]*>/i, metaTag);
  } else if (/<head[^>]*>/i.test(rawHtml)) {
    return rawHtml.replace(/<head[^>]*>/i, (match) => `${match}\n    ${metaTag}`);
  } else if (/<html[^>]*>/i.test(rawHtml)) {
    return rawHtml.replace(/<html[^>]*>/i, (match) => `${match}\n<head>\n    ${metaTag}\n</head>`);
  } else {
    return `<!DOCTYPE html>\n<html>\n<head>\n    ${metaTag}\n</head>\n<body>\n${rawHtml}\n</body>\n</html>`;
  }
}

/**
 * Safely render Markdown content into sanitized HTML.
 * Unsanitized generated content is NEVER injected into the application DOM.
 * Strips scripts, event handlers, iframes, and dangerous attributes.
 */
export function renderSanitizedMarkdown(markdownContent, customPurifyInstance = null) {
  if (!markdownContent) return "";
  const rawHtml = marked.parse(markdownContent);
  const purifier = customPurifyInstance || getDOMPurify();

  // Strict sanitization with DOMPurify
  return purifier.sanitize(rawHtml, {
    USE_PROFILES: { html: true },
    FORBID_TAGS: [
      'script',
      'iframe',
      'object',
      'embed',
      'form',
      'input',
      'button',
      'base',
      'meta',
      'link'
    ],
    FORBID_ATTR: [
      'onerror',
      'onload',
      'onclick',
      'onmouseover',
      'onfocus',
      'onblur',
      'style'
    ],
  });
}
