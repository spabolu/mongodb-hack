// === POLISHED COMMUNITY NOTE FOR REDDIT ===
// Works on both feed and single-post pages

function addNoteToPost(post) {
  // Extract data (same reliable selectors as before)
  const titleElement =
    post.querySelector('h1') ||
    post.querySelector('a[data-testid="post-title"]') ||
    post.querySelector('h3');
  const title = titleElement
    ? titleElement.textContent.trim()
    : 'No title found';

  const urlElement =
    post.querySelector('a[slot="full-post-link"]') ||
    post.querySelector('a[href^="http"]:not([href*="reddit.com"])') ||
    post.querySelector('a.external');
  const url = urlElement ? urlElement.href : 'No URL found';

  const subtextElement =
    post.querySelector('div[slot="text-body"]') ||
    post.querySelector('div[data-testid="post-text-body"]') ||
    post.querySelector('div[class*="RichTextJSON-root"]') ||
    post.querySelector('div.usertext-body') ||
    post.querySelector('div.md');
  const subtext = subtextElement
    ? subtextElement.textContent.trim().substring(0, 300) +
      (subtextElement.textContent.trim().length > 300 ? '…' : '')
    : 'No subtext found';

  // === Create the beautiful Community Note ===
  const noteDiv = document.createElement('div');
  noteDiv.className = 'reddit-community-note'; // For duplicate prevention

  noteDiv.style.cssText = `
    margin: 16px 0;
    padding: 16px;
    background: #ffffff;
    border: 1px solid #cfd8e3;
    border-radius: 12px;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    font-size: 14px;
    line-height: 1.5;
    color: #1c1c1c;
    box-shadow: 0 1px 3px rgba(0,0,0,0.05);
  `;

  noteDiv.innerHTML = `
    <div style="display:flex; align-items:center; gap:8px; margin-bottom:12px; font-weight:600; color:#1a1a1b;">
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#1d9bf0" stroke-width="2.5" style="flex-shrink:0;">
        <path d="M12 2a10 10 0 100 20 10 10 0 000-20z"></path>
        <path d="M12 8v4"></path>
        <circle cx="12" cy="16" r="1"></circle>
      </svg>
      Community Note
    </div>

    <div style="color:#57606a; margin-bottom:12px;">
      Readers added context they thought people might want to know.
    </div>

    ${
      title !== 'No title found'
        ? `
      <div style="margin-bottom:8px;">
        <strong>Title:</strong> ${escapeHtml(title)}
      </div>`
        : ''
    }

    ${
      url !== 'No URL found'
        ? `
      <div style="margin-bottom:8px;">
        <strong>Source URL:</strong> 
        <a href="${url}" target="_blank" rel="noopener" style="color:#1a0dab; text-decoration:none;">
          ${url
            .replace(/^https?:\/\//, '')
            .replace(/\/$/, '')
            .substring(0, 60)}${url.length > 60 ? '…' : ''}
        </a>
      </div>`
        : ''
    }

    ${
      subtext !== 'No subtext found'
        ? `
      <div>
        <strong>Post text:</strong> ${escapeHtml(subtext)}
      </div>`
        : ''
    }
      
    <div style="margin-top:16px; font-size:12px; color:#57606a;">
      This is a demo extension • Context is shown automatically
    </div>
  `;

  // Insert right above the engagement bar
  const upvoteButton = post.querySelector(
    'button[aria-label="Upvote"], button[data-click-id="upvote"]'
  );
  if (upvoteButton) {
    const engagementBar =
      upvoteButton.closest(
        'div[style*="flex"], div[data-testid="post-footer"]'
      ) || post.lastChild;
    post.insertBefore(noteDiv, engagementBar);
  } else {
    post.appendChild(noteDiv);
  }
}

// Simple HTML escape (security)
function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

// Process posts
function processPosts() {
  document.querySelectorAll('shreddit-post').forEach((post) => {
    if (!post.querySelector('.reddit-community-note')) {
      addNoteToPost(post);
    }
  });
}

// Run on load + observe changes
setTimeout(processPosts, 1000);
const observer = new MutationObserver(() => setTimeout(processPosts, 500));
observer.observe(document.body, { childList: true, subtree: true });
