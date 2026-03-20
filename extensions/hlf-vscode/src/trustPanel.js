const vscode = require('vscode');

function escapeHtml(value) {
  return String(value)
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;');
}

class TrustPanel {
  constructor(extensionUri) {
    this.extensionUri = extensionUri;
    this.panel = undefined;
  }

  show(title, sections) {
    if (!this.panel) {
      this.panel = vscode.window.createWebviewPanel(
        'hlfTrustPanel',
        title,
        vscode.ViewColumn.Beside,
        { enableFindWidget: true },
      );
      this.panel.onDidDispose(() => {
        this.panel = undefined;
      });
    }

    this.panel.title = title;
    this.panel.webview.html = this.renderHtml(title, sections);
    this.panel.reveal(vscode.ViewColumn.Beside, true);
  }

  renderHtml(title, sections) {
    const sectionMarkup = sections.map((section) => {
      const payload = typeof section.body === 'string'
        ? section.body
        : JSON.stringify(section.body, null, 2);
      return `
        <section class="card">
          <h2>${escapeHtml(section.title)}</h2>
          <p class="subtitle">${escapeHtml(section.subtitle || '')}</p>
          <pre>${escapeHtml(payload)}</pre>
        </section>
      `;
    }).join('\n');

    return `<!DOCTYPE html>
      <html lang="en">
        <head>
          <meta charset="UTF-8" />
          <meta name="viewport" content="width=device-width, initial-scale=1.0" />
          <title>${escapeHtml(title)}</title>
          <style>
            :root {
              color-scheme: light dark;
              --bg: #0f1720;
              --panel: #182430;
              --text: #edf2f7;
              --muted: #9fb3c8;
              --accent: #7dd3fc;
              --border: #274154;
            }
            body {
              margin: 0;
              padding: 24px;
              background: linear-gradient(180deg, #0b1218 0%, #111d27 100%);
              color: var(--text);
              font-family: Consolas, 'Courier New', monospace;
            }
            h1 {
              margin-top: 0;
              font-size: 20px;
            }
            .grid {
              display: grid;
              grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
              gap: 16px;
            }
            .card {
              border: 1px solid var(--border);
              border-radius: 12px;
              background: rgba(24, 36, 48, 0.92);
              padding: 16px;
              box-shadow: 0 10px 30px rgba(0, 0, 0, 0.25);
            }
            h2 {
              margin: 0 0 8px 0;
              color: var(--accent);
              font-size: 15px;
            }
            .subtitle {
              margin: 0 0 12px 0;
              color: var(--muted);
              font-size: 12px;
            }
            pre {
              margin: 0;
              white-space: pre-wrap;
              word-break: break-word;
              font-size: 12px;
              line-height: 1.5;
            }
          </style>
        </head>
        <body>
          <h1>${escapeHtml(title)}</h1>
          <div class="grid">${sectionMarkup}</div>
        </body>
      </html>`;
  }
}

module.exports = {
  TrustPanel,
};