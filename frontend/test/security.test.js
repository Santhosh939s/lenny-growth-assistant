import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { JSDOM } from 'jsdom';
import DOMPurifyModule from 'dompurify';
import {
  requiresScript,
  getIframeSandbox,
  getCSPDirectives,
  prepareHtmlArtifact,
  renderSanitizedMarkdown
} from '../src/utils/security.js';

describe('Milestone 6 Security & Browser Configuration Tests', () => {
  // Setup JSDOM environment
  const dom = new JSDOM('<!DOCTYPE html><html><head></head><body><div id="root"></div></body></html>');
  const window = dom.window;
  const document = window.document;
  const DOMPurify = DOMPurifyModule(window);

  describe('1. DOMPurify Markdown DOM Injection & Sanitization', () => {
    test('Unsanitized generated content is NEVER injected into application DOM', () => {
      const maliciousMarkdown = `
# Safe Title
Normal text paragraph.

<script>window.__pwned__ = true;</script>
<img src="invalid-image.png" onerror="window.__pwned__ = true;" />
<svg onload="window.__pwned__ = true;"></svg>
<iframe src="http://attacker.example.com/exploit"></iframe>
<form action="http://attacker.example.com/steal"><button>Submit</button></form>
<a href="javascript:alert('xss')">Malicious Link</a>
      `.trim();

      const sanitizedHtml = renderSanitizedMarkdown(maliciousMarkdown, DOMPurify);
      
      // Inject sanitized output into real DOM element
      const container = document.createElement('div');
      container.innerHTML = sanitizedHtml;

      // Verify no script elements exist in the DOM
      const scripts = container.querySelectorAll('script');
      assert.equal(scripts.length, 0, 'No <script> tags should exist in DOM');

      // Verify no iframe elements exist in the DOM
      const iframes = container.querySelectorAll('iframe');
      assert.equal(iframes.length, 0, 'No <iframe> tags should exist in DOM');

      // Verify no form elements exist in the DOM
      const forms = container.querySelectorAll('form');
      assert.equal(forms.length, 0, 'No <form> tags should exist in DOM');

      // Verify all dangerous event attributes are stripped
      const allElements = container.querySelectorAll('*');
      for (const el of allElements) {
        assert.equal(el.hasAttribute('onerror'), false, `Element ${el.tagName} has onerror`);
        assert.equal(el.hasAttribute('onload'), false, `Element ${el.tagName} has onload`);
        assert.equal(el.hasAttribute('onclick'), false, `Element ${el.tagName} has onclick`);
        assert.equal(el.hasAttribute('onmouseover'), false, `Element ${el.tagName} has onmouseover`);
      }

      // Verify javascript: URLs are stripped from links
      const link = container.querySelector('a');
      if (link) {
        const href = link.getAttribute('href') || '';
        assert.ok(!href.toLowerCase().startsWith('javascript:'), 'Link href must not be javascript: URI');
      }

      // Verify safe content remains
      const h1 = container.querySelector('h1');
      assert.ok(h1, 'Heading 1 must remain');
      assert.equal(h1.textContent, 'Safe Title');
    });
  });

  describe('2. Iframe Sandboxing Least Privilege', () => {
    test('Static HTML uses the most restrictive sandbox possible (empty string)', () => {
      const staticHtml = `
<!DOCTYPE html>
<html>
<head><style>h1 { color: blue; }</style></head>
<body><h1>Static Report</h1><p>No scripts needed</p></body>
</html>
      `;

      assert.equal(requiresScript(staticHtml), false);
      const sandboxAttr = getIframeSandbox(staticHtml);
      assert.equal(sandboxAttr, '', 'Static HTML must use empty sandbox for maximum restriction');

      // Test on DOM iframe element
      const iframe = document.createElement('iframe');
      iframe.setAttribute('sandbox', sandboxAttr);

      const sandboxValue = iframe.getAttribute('sandbox') || '';
      const tokens = sandboxValue.split(/\s+/).filter(Boolean);

      // Verify restrictive state: NO tokens at all
      assert.equal(tokens.length, 0, 'Most restrictive sandbox must have 0 allowed capabilities');
      assert.equal(tokens.includes('allow-scripts'), false);
      assert.equal(tokens.includes('allow-same-origin'), false);
      assert.equal(tokens.includes('allow-top-navigation'), false);
      assert.equal(tokens.includes('allow-forms'), false);
      assert.equal(tokens.includes('allow-popups'), false);
    });

    test('Script HTML uses ONLY allow-scripts and NEVER allow-same-origin or navigation', () => {
      const scriptHtml = `
<!DOCTYPE html>
<html>
<head><title>Interactive Chart</title></head>
<body>
  <div id="chart"></div>
  <script>console.log('rendering chart');</script>
</body>
</html>
      `;

      assert.equal(requiresScript(scriptHtml), true);
      const sandboxAttr = getIframeSandbox(scriptHtml);
      assert.equal(sandboxAttr, 'allow-scripts');

      // Test on DOM iframe element
      const iframe = document.createElement('iframe');
      iframe.setAttribute('sandbox', sandboxAttr);

      const sandboxValue = iframe.getAttribute('sandbox') || '';
      const tokens = sandboxValue.split(/\s+/).filter(Boolean);

      // MUST have allow-scripts
      assert.equal(tokens.includes('allow-scripts'), true);

      // MUST NOT have any of the following dangerous permissions
      assert.equal(tokens.includes('allow-same-origin'), false, 'NEVER grant allow-same-origin');
      assert.equal(tokens.includes('allow-top-navigation'), false, 'NEVER grant allow-top-navigation');
      assert.equal(tokens.includes('allow-forms'), false, 'NEVER grant allow-forms');
      assert.equal(tokens.includes('allow-popups'), false, 'NEVER grant allow-popups');
      assert.equal(tokens.includes('allow-modals'), false, 'NEVER grant allow-modals');
    });
  });

  describe('3. Content Security Policy (CSP) Directives', () => {
    test('Static HTML CSP strictly blocks network, scripts, and forms', () => {
      const rawHtml = '<html><head><title>Test</title></head><body><h1>Hello</h1></body></html>';
      const prepared = prepareHtmlArtifact(rawHtml);

      // Parse with JSDOM
      const artifactDom = new JSDOM(prepared);
      const metaCsp = artifactDom.window.document.querySelector('meta[http-equiv="Content-Security-Policy"]');
      assert.ok(metaCsp, 'CSP meta tag must be present');

      const content = metaCsp.getAttribute('content');
      assert.ok(content.includes("default-src 'none'"), 'Must include default-src none');
      assert.ok(content.includes("style-src 'unsafe-inline'"), 'Must allow embedded styles');
      assert.ok(content.includes("img-src data:"), 'Must only allow data: images');
      assert.ok(content.includes("font-src data:"), 'Must only allow data: fonts');
      assert.ok(content.includes("connect-src 'none'"), 'Must block all network requests (fetch/XHR/WS)');
      assert.ok(content.includes("form-action 'none'"), 'Must block all form actions');
      assert.ok(content.includes("base-uri 'none'"), 'Must block base URI hijacking');
      assert.ok(content.includes("script-src 'none'"), 'Static HTML must use script-src none');
    });

    test('Script HTML CSP allows inline script execution but blocks network and forms', () => {
      const rawHtml = '<html><head></head><body><script>alert(1)</script></body></html>';
      const prepared = prepareHtmlArtifact(rawHtml);

      const artifactDom = new JSDOM(prepared);
      const metaCsp = artifactDom.window.document.querySelector('meta[http-equiv="Content-Security-Policy"]');
      assert.ok(metaCsp, 'CSP meta tag must be present');

      const content = metaCsp.getAttribute('content');
      assert.ok(content.includes("script-src 'unsafe-inline'"), 'Should allow inline script');
      assert.ok(content.includes("connect-src 'none'"), 'Must block connect-src (network requests)');
      assert.ok(content.includes("form-action 'none'"), 'Must block form-action');
      assert.ok(content.includes("default-src 'none'"), 'Must block default-src');
    });
  });
});
