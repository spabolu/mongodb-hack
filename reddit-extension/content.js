// Main function: adds a verification note to a Reddit post
async function addNoteToPost(post) {
  // Get subreddit from URL first (fallback method)
  const currentUrl = window.location.href;
  const urlMatch = currentUrl.match(/\/r\/([^\/]+)/);
  const subreddit = urlMatch ? urlMatch[1] : null;

  // Better method: extract subreddit directly from the post element
  const subredditElement = post.querySelector(
    'a[data-testid="subreddit-link"], a[href^="/r/"]'
  );
  const postSubreddit = subredditElement
    ? subredditElement.getAttribute('href').match(/\/r\/([^\/]+)/)?.[1]
    : null;

  // Use post-level subreddit if available, otherwise fall back to URL
  const finalSubreddit = postSubreddit || subreddit;

  // Only run verification on specific subreddits
  if (
    finalSubreddit !== 'news' &&
    finalSubreddit !== 'politics' &&
    finalSubreddit !== 'TheOnion'
  ) {
    return;
  }

  // Extract post date - Reddit uses different elements, so try multiple selectors
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

  // Parse the date - prefer ISO format from attributes, fall back to text
  let postDate = 'No date found';
  if (timeElement) {
    const datetime =
      timeElement.getAttribute('datetime') ||
      timeElement.getAttribute('ts') ||
      timeElement.getAttribute('title');

    if (datetime) {
      postDate = datetime; // ISO timestamp is better for API
    } else {
      postDate = timeElement.textContent.trim(); // Relative time like "2 hours ago"
    }
  }

  // Debug logging for date extraction
  console.log('Post Date:', postDate);
  console.log('Time Element Found:', timeElement);
  console.log('Time Element HTML:', timeElement?.outerHTML);
  // Get post title - try common title selectors
  const titleElement =
    post.querySelector('h1') ||
    post.querySelector('a[data-testid="post-title"]') ||
    post.querySelector('h3');
  const title = titleElement
    ? titleElement.textContent.trim()
    : 'No title found';

  // Find external URL for link posts (exclude Reddit internal links)
  const urlElement =
    post.querySelector('a[slot="full-post-link"]') ||
    post.querySelector('a[data-testid="outbound-link"]') ||
    post.querySelector(
      'a[href^="http"]:not([href*="reddit.com"]):not([href*="redd.it"])'
    ) ||
    post.querySelector('a.external') ||
    post.querySelector(
      'a[target="_blank"]:not([href*="reddit.com"]):not([href*="redd.it"])'
    );
  const url = urlElement ? urlElement.href : 'No URL found';

  // Extract post body text (for self-posts/text posts)
  // Reddit's DOM structure varies, so we try many selectors
  const subtextElement =
    post.querySelector('div[slot="text-body"]') ||
    post.querySelector('div[data-testid="post-text-body"]') ||
    post.querySelector('div[class*="RichTextJSON-root"]') ||
    post.querySelector('div.usertext-body') ||
    post.querySelector('div.md') ||
    post.querySelector('div[data-testid="post-content"]') ||
    post
      .querySelector('shreddit-async-loader[slot="text-body"]')
      ?.querySelector('div');
  // Limit to 300 chars to keep API payload reasonable
  const subtext = subtextElement
    ? subtextElement.textContent.trim().substring(0, 300) +
    (subtextElement.textContent.trim().length > 300 ? '…' : '')
    : 'No subtext found';

  // Debug logging
  console.log('[Reddit Community Notes] Post data:', {
    subreddit: finalSubreddit,
    title,
    url,
    hasSubtext: subtext !== 'No subtext found',
    postDate,
  });

  // Handle text posts vs link posts
  // Link posts have external URLs, text posts need the Reddit post URL
  let finalUrl = url;
  if (url === 'No URL found') {
    // This is a self-post, so use the Reddit post permalink
    const redditPostLink =
      post.querySelector('a[data-testid="post-title"]') ||
      post.querySelector('h1 a') ||
      post.querySelector('a[href*="/comments/"]');
    if (redditPostLink) {
      const href = redditPostLink.getAttribute('href');
      // Handle both absolute and relative URLs
      finalUrl = href?.startsWith('http')
        ? href
        : `https://www.reddit.com${href}`;
      console.log(
        '[Reddit Community Notes] Text post detected, using Reddit URL:',
        finalUrl
      );
    } else {
      // Last resort: use current page URL (for single post pages)
      finalUrl = window.location.href.split('?')[0]; // Strip query params
      console.log('[Reddit Community Notes] Using current page URL:', finalUrl);
    }
  }

  // Create the note element with loading state
  // We'll update this with results once the API call completes
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
      AI Community Notes
    </div>
    <div style="color:#57606a;">Verifying...</div>
  `;

  // Insert the note into the DOM
  // Reddit's layout changes frequently, so we try multiple insertion strategies
  const upvoteButton = post.querySelector(
    'button[aria-label="Upvote"], button[data-click-id="upvote"]'
  );

  // Array of functions that try different insertion points
  // Each returns a target element or null
  const insertionTargets = [
    () => {
      // Try to find post footer first
      const footer =
        post.querySelector('div[data-testid="post-footer"]') ||
        post.querySelector('footer') ||
        post.querySelector('div[class*="footer"]');
      if (footer) return footer;
    },
    () => {
      // Try to find engagement bar near upvote button
      if (upvoteButton) {
        const engagementBar = upvoteButton.closest(
          'div[style*="flex"], div[data-testid="post-footer"]'
        );
        if (engagementBar) return engagementBar;
      }
    },
    () => {
      // For single post pages, insert after content
      const content =
        post.querySelector('div[data-testid="post-content"]') ||
        post.querySelector('div[slot="text-body"]') ||
        post.querySelector('article > div');
      if (content) return content.nextElementSibling || content.parentElement;
    },
    () => post.lastElementChild || post, // Last resort: end of post
  ];

  // Try each insertion strategy until one works
  let inserted = false;
  for (const getTarget of insertionTargets) {
    const target = getTarget();
    if (target && target.parentElement) {
      try {
        target.parentElement.insertBefore(noteDiv, target.nextSibling);
        inserted = true;
        break;
      } catch (e) {
        console.log(
          '[Reddit Community Notes] Insertion failed, trying next method:',
          e
        );
      }
    }
  }

  // If all strategies failed, just append to the post
  if (!inserted) {
    post.appendChild(noteDiv);
  }

  // Call the verification API
  try {
    console.log('[Reddit Community Notes] Sending verification request:', {
      url: finalUrl,
      title: title.substring(0, 50),
      hasSubtext: subtext !== 'No subtext found',
    });

    const response = await fetch('https://cef5c5f9c1f3.ngrok-free.app/verify', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        url: finalUrl,
        title: title,
        subtext: subtext,
        postDate: postDate,
      }),
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const data = await response.json();
    console.log('[Reddit Community Notes] Received response:', data);

    // Determine status color and text based on verification result
    const isCorrect = data.is_correct;
    const statusColor =
      isCorrect === true
        ? '#28a745'  // Green for correct
        : isCorrect === false
          ? '#dc3545'  // Red for incorrect
          : '#6c757d'; // Gray for unknown
    const statusText =
      isCorrect === true
        ? 'Correct'
        : isCorrect === false
          ? 'Not Correct'
          : 'Unable to Verify';

    // Update the note with verification results
    noteDiv.innerHTML = `
      <div style="display:flex; align-items:center; gap:8px; margin-bottom:12px; font-weight:600; color:#1a1a1b;">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#1d9bf0" stroke-width="2.5" style="flex-shrink:0;">
          <path d="M12 2a10 10 0 100 20 10 10 0 000-20z"></path>
          <path d="M12 8v4"></path>
          <circle cx="12" cy="16" r="1"></circle>
        </svg>
        AI Community Notes
      </div>

      <div style="margin-bottom:16px;">
        <strong style="color:#1a1a1b;">Verification Result</strong>
        <div style="margin-top:8px; padding:8px; background:${statusColor}15; border-left:3px solid ${statusColor}; border-radius:4px;">
          <div style="font-weight:600; color:${statusColor}; margin-bottom:4px;">${statusText}</div>
          <div style="color:#1c1c1c; white-space:pre-line;">${escapeHtml(
      data.explanation || 'No explanation available'
    )}</div>
        </div>
      </div>

      <div style="margin-top:16px; padding-top:16px; border-top:1px solid #e1e4e8;">
        <strong style="color:#1a1a1b; display:block; margin-bottom:8px;">Sources & References</strong>
        ${data.sources && data.sources.length > 0
        ? data.sources
          .map(
            (source) => `
              <div style="margin-bottom:16px;">
                <div style="margin-bottom:4px;">
                  <a href="${escapeHtml(
              source.source_url
            )}" target="_blank" rel="noopener" style="color:#1a0dab; text-decoration:none; word-break:break-all;">
                    ${escapeHtml(
              source.source_url
                .replace(/^https?:\/\//, '')
                .replace(/\/$/, '')
                .substring(0, 60)
            )}${source.source_url.length > 60 ? '…' : ''}
                  </a>
                </div>
                <div style="color:#57606a; font-size:13px; margin-top:4px;">
                  ${escapeHtml(
              source.source_description || 'No description available'
            )}
                </div>
              </div>
            `
          )
          .join('')
        : `
              <div style="margin-bottom:16px;">
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
            `
      }
      </div>
    `;
  } catch (error) {
    // Show error message if API call fails
    console.error('[Reddit Community Notes] Error verifying content:', error);
    noteDiv.innerHTML = `
      <div style="display:flex; align-items:center; gap:8px; margin-bottom:12px; font-weight:600; color:#1a1a1b;">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#dc3545" stroke-width="2.5" style="flex-shrink:0;">
          <path d="M12 2a10 10 0 100 20 10 10 0 000-20z"></path>
          <path d="M12 8v4"></path>
          <circle cx="12" cy="16" r="1"></circle>
        </svg>
        AI Community Notes
      </div>
      <div style="color:#dc3545;">Error: Unable to verify content. ${escapeHtml(
      error.message
    )}</div>
      <div style="color:#57606a; font-size:12px; margin-top:8px;">Check console for details. Make sure the backend is running on http://localhost:8000</div>
    `;
  }
}

// Escape HTML to prevent XSS attacks
// Uses browser's built-in escaping by setting textContent
function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

// Find all posts on the page and add notes to them
async function processPosts() {
  // Reddit uses different selectors for posts depending on layout
  // Try each one until we find posts
  const postSelectors = [
    'shreddit-post',  // New Reddit layout
    'div[data-testid="post-container"]',
    'div[class*="Post"]',
    'article[data-testid="post-container"]',
  ];

  let posts = [];
  for (const selector of postSelectors) {
    posts = document.querySelectorAll(selector);
    if (posts.length > 0) {
      console.log(
        `[Reddit Community Notes] Found ${posts.length} posts using selector: ${selector}`
      );
      break;
    }
  }

  if (posts.length === 0) {
    console.log('[Reddit Community Notes] No posts found with any selector');
    return;
  }

  // Process each post (skip if it already has a note to avoid duplicates)
  for (const post of posts) {
    if (!post.querySelector('.reddit-community-note')) {
      console.log('[Reddit Community Notes] Processing post:', post);
      await addNoteToPost(post);
    }
  }
}

// Script initialization
console.log('[Reddit Community Notes] Content script loaded');

// Run processing when page is ready
function runProcessing() {
  // Wait for DOM to be ready if it's still loading
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
      setTimeout(processPosts, 500);
    });
  } else {
    // DOM is already ready, just wait a bit for Reddit's JS to finish
    setTimeout(processPosts, 500);
  }
}

// Initial run when script loads
runProcessing();

// Also run after a longer delay to catch lazy-loaded content
setTimeout(processPosts, 2000);

// Watch for new posts added dynamically (Reddit uses infinite scroll)
// Debounce with 500ms delay to avoid processing too frequently
const observer = new MutationObserver(() => {
  setTimeout(processPosts, 500);
});
observer.observe(document.body, { childList: true, subtree: true });
