// === POLISHED COMMUNITY NOTE FOR REDDIT ===
// Works on both feed and single-post pages

async function addNoteToPost(post) {
  const currentUrl = window.location.href; // ← Changed from 'url' to 'currentUrl'
  const urlMatch = currentUrl.match(/\/r\/([^\/]+)/); // ← Use 'currentUrl' here
  const subreddit = urlMatch ? urlMatch[1] : null;

  // Method 2: Check post element for subreddit link
  const subredditElement = post.querySelector(
    'a[data-testid="subreddit-link"], a[href^="/r/"]'
  );
  const postSubreddit = subredditElement
    ? subredditElement.getAttribute('href').match(/\/r\/([^\/]+)/)?.[1]
    : null;

  const finalSubreddit = postSubreddit || subreddit;

  // Only process r/news and r/politics
  if (finalSubreddit !== 'news' && finalSubreddit !== 'politics') {
    return;
  }

  // Extract data
  const timeElement =
    post.querySelector('time[datetime]') ||
    post.querySelector('faceplate-timeago[ts]') ||
    post.querySelector('span[data-testid="post_timestamp"]') ||
    post.querySelector('time') ||
    post.querySelector('span:has-text("ago")') ||
    Array.from(post.querySelectorAll('span, time')).find(
      (el) =>
        el.textContent.includes('ago') &&
        el.textContent.match(/\d+\s*(mo|h|d|m|y|s)\s*ago/i)
    );

  let postDate = 'No date found';
  if (timeElement) {
    // Try to get the datetime attribute first (ISO format)
    const datetime =
      timeElement.getAttribute('datetime') ||
      timeElement.getAttribute('ts') ||
      timeElement.getAttribute('title');

    if (datetime) {
      postDate = datetime; // ISO timestamp
    } else {
      // Fall back to the relative time text
      postDate = timeElement.textContent.trim();
    }
  }

  // Add this for debugging:
  console.log('Post Date:', postDate);
  console.log('Time Element Found:', timeElement);
  console.log('Time Element HTML:', timeElement?.outerHTML);
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

  // Skip if no URL found
  if (url === 'No URL found') {
    return;
  }

  // Create loading note
  const noteDiv = document.createElement('div');
  noteDiv.className = 'reddit-community-note';
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
      AI Truth Checker
    </div>
    <div style="color:#57606a;">Verifying...</div>
  `;

  // Insert loading note
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

  // Call API
  try {
    const response = await fetch('http://localhost:8000/verify', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        url: url,
        title: title,
        subtext: subtext,
        postDate: postDate,
      }),
    });

    const data = await response.json();

    // Update note with formatted output
    const isCorrect = data.is_correct;
    const statusColor =
      isCorrect === true
        ? '#28a745'
        : isCorrect === false
        ? '#dc3545'
        : '#6c757d';
    const statusText =
      isCorrect === true
        ? 'Correct'
        : isCorrect === false
        ? 'Not Correct'
        : 'Unable to Verify';

    noteDiv.innerHTML = `
      <div style="display:flex; align-items:center; gap:8px; margin-bottom:12px; font-weight:600; color:#1a1a1b;">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#1d9bf0" stroke-width="2.5" style="flex-shrink:0;">
          <path d="M12 2a10 10 0 100 20 10 10 0 000-20z"></path>
          <path d="M12 8v4"></path>
          <circle cx="12" cy="16" r="1"></circle>
        </svg>
        AI Truth Checker
      </div>

      <div style="margin-bottom:16px;">
        <strong style="color:#1a1a1b;">Is the post correct or not?</strong>
        <div style="margin-top:8px; padding:8px; background:${statusColor}15; border-left:3px solid ${statusColor}; border-radius:4px;">
          <div style="font-weight:600; color:${statusColor}; margin-bottom:4px;">${statusText}</div>
          <div style="color:#1c1c1c; white-space:pre-line;">${escapeHtml(
            data.explanation || 'No explanation available'
          )}</div>
        </div>
      </div>

      <div style="margin-top:16px; padding-top:16px; border-top:1px solid #e1e4e8;">
        <strong style="color:#1a1a1b; display:block; margin-bottom:8px;">What sources were used to validate?</strong>
        <div style="margin-bottom:4px;">
          <a href="${escapeHtml(
            data.source_url || url
          )}" target="_blank" rel="noopener" style="color:#1a0dab; text-decoration:none; word-break:break-all;">
            ${escapeHtml(
              (data.source_url || url)
                .replace(/^https?:\/\//, '')
                .replace(/\/$/, '')
                .substring(0, 60)
            )}${(data.source_url || url).length > 60 ? '…' : ''}
          </a>
        </div>
        <div style="color:#57606a; font-size:13px; margin-top:4px;">
          ${escapeHtml(
            data.source_description || 'No source description available'
          )}
        </div>
      </div>
    `;
  } catch (error) {
    noteDiv.innerHTML = `
      <div style="display:flex; align-items:center; gap:8px; margin-bottom:12px; font-weight:600; color:#1a1a1b;">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#dc3545" stroke-width="2.5" style="flex-shrink:0;">
          <path d="M12 2a10 10 0 100 20 10 10 0 000-20z"></path>
          <path d="M12 8v4"></path>
          <circle cx="12" cy="16" r="1"></circle>
        </svg>
        AI Truth Checker
      </div>
      <div style="color:#dc3545;">Error: Unable to verify content. ${error.message}</div>
    `;
  }
}

// Simple HTML escape (security)
function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

// Process posts
async function processPosts() {
  const posts = document.querySelectorAll('shreddit-post');
  for (const post of posts) {
    if (!post.querySelector('.reddit-community-note')) {
      await addNoteToPost(post);
    }
  }
}

// Run on load + observe changes
setTimeout(processPosts, 1000);
const observer = new MutationObserver(() => setTimeout(processPosts, 500));
observer.observe(document.body, { childList: true, subtree: true });
