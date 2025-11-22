(async function () {
    'use strict';

    // ————————————————————————————————
    // CONFIGURATION & UTILS
    // ————————————————————————————————
    const SELECTORS = {
        postComponent: 'shreddit-post',
        titleSlot: '[slot="title"]',
        textSlot: '[slot="text-body"]',
        mediaSlot: '[slot="post-media-container"]',
        creditBar: '[slot="credit-bar"]'
    };

    function waitForPost() {
        return new Promise(resolve => {
            const start = Date.now();
            const check = () => {
                // We look for the main post component which contains all data attributes
                const post = document.querySelector(SELECTORS.postComponent);
                if (post) resolve(post);
                else if (Date.now() - start > 15000) {
                    console.log('[TruthGuardian] Timeout: shreddit-post not found');
                    resolve(null);
                } else requestAnimationFrame(check);
            };
            check();
        });
    }

    // Determine where to visually place the note. 
    // Best spot: After the title, before the media/body.
    function getInjectionPoint(post) {
        const titleEl = post.querySelector(SELECTORS.titleSlot);
        return titleEl ? titleEl.nextElementSibling : post.firstElementChild;
    }

    function createNote() {
        const div = document.createElement('div');
        div.className = 'truthguardian-note';
        // Add some basic inline styles to ensure it pops out immediately
        div.style.cssText = `
        margin: 12px 0; 
        padding: 12px; 
        border-left: 4px solid #ff4500; 
        background: var(--color-neutral-background-weak, #f6f7f8);
        color: var(--color-neutral-content, #1c1c1c);
        font-family: sans-serif;
        border-radius: 4px;
      `;
        div.innerHTML = `<span class="loading">⛨ TruthGuardian is analyzing this post...</span>`;
        return div;
    }

    // ————————————————————————————————
    // DATA EXTRACTION (2025 Shreddit UI)
    // ————————————————————————————————
    function extractPostData(post) {
        // 1. METADATA FROM ATTRIBUTES (Most Reliable)
        // The <shreddit-post> tag contains these attributes directly
        const rawTitle = post.getAttribute('post-title');
        const rawUrl = post.getAttribute('content-href');
        const permalink = post.getAttribute('permalink');
        const postType = post.getAttribute('post-type'); // 'link', 'text', 'image', etc.

        const data = {
            title: rawTitle || "No title found",
            type: postType || "unknown",
            text: "",
            articleUrl: null,
            mediaUrls: [],
            redditUrl: permalink ? `https://www.reddit.com${permalink}` : location.href
        };

        // 2. FALLBACK TITLE EXTRACTION
        // If attribute is missing, check the h1 slot
        if (!rawTitle) {
            const titleSlot = post.querySelector(SELECTORS.titleSlot);
            if (titleSlot) data.title = titleSlot.innerText.trim();
        }

        // 3. BODY TEXT EXTRACTION
        // Specifically look for the div assigned to the 'text-body' slot
        const textSlot = post.querySelector(SELECTORS.textSlot);
        if (textSlot) {
            data.text = textSlot.innerText.trim();
            if (data.type === 'unknown') data.type = 'text';
        }

        // 4. EXTERNAL LINK (Article)
        // If 'content-href' exists and isn't a relative reddit link, it's the article
        if (rawUrl && !rawUrl.startsWith('/') && !rawUrl.includes('reddit.com')) {
            data.articleUrl = rawUrl;
            // Update type if it wasn't set correctly by attributes
            if (data.type === 'unknown' || data.type === 'text') {
                data.type = data.text ? 'text+link' : 'link';
            }
        }

        // 5. MEDIA EXTRACTION
        // Look inside the container specifically reserved for media
        const mediaContainer = post.querySelector(SELECTORS.mediaSlot);
        if (mediaContainer) {
            // Get standard images
            const images = mediaContainer.querySelectorAll('img');
            images.forEach(img => {
                if (img.src) data.mediaUrls.push(img.src);
            });

            // Get Shreddit video player preview images
            const videoPlayer = mediaContainer.querySelector('shreddit-player-2');
            if (videoPlayer && videoPlayer.getAttribute('poster')) {
                data.mediaUrls.push(videoPlayer.getAttribute('poster'));
                data.type = 'video';
            }
        }

        return data;
    }

    // ————————————————————————————————
    // MOCK AI LOGIC (REPLACE WITH REAL API CALL)
    // ————————————————————————————————
    const mocks = [
        { note: "⚠️ Context Missing: While an arrest warrant was issued, local sources indicate Bolsonaro has not yet been taken into physical custody.", sources: ["Reuters", "BBC", "Folha de S.Paulo"] },
        { note: "✅ Verified: Multiple agencies confirm the subject was detained by Federal Police at 10:00 AM local time.", sources: ["AP News", "CNN", "O Globo"] },
        { note: "❌ Misleading: The image used in this post is from a 2022 rally, not from today's events.", sources: ["AFP Fact Check", "Snopes"] },
        { note: "🤡 Satire: This post originates from a known parody account.", sources: ["TruthGuardian DB"] }
    ];

    function getMockResponse(d) {
        const t = d.title.toLowerCase();
        if (t.includes("bolsonaro") && (t.includes("arrested") || t.includes("detained"))) return mocks[0]; // Example scenario
        if (t.includes("confirmed") || t.includes("official")) return mocks[1];
        if (d.mediaUrls.length > 0) return mocks[2];
        return mocks[Math.floor(Math.random() * mocks.length)];
    }

    // ————————————————————————————————
    // EXECUTION
    // ————————————————————————————————
    const post = await waitForPost();
    if (!post) return;

    // Prevent duplicate injections
    if (post.querySelector('.truthguardian-note')) return;

    const injectAt = getInjectionPoint(post);
    const noteEl = createNote();

    // Inject the note into the Light DOM of the shreddit-post
    if (injectAt) {
        injectAt.parentNode.insertBefore(noteEl, injectAt);
    } else {
        post.prepend(noteEl);
    }

    // Extract Data
    const postData = extractPostData(post);

    // Debug Output
    console.clear();
    console.group('%c TruthGuardian Analysis ', 'background:#0079d3; color:white; padding:4px 8px; border-radius:4px;');
    console.log('Title:', postData.title);
    console.log('Type:', postData.type.toUpperCase());
    console.log('Reddit Link:', postData.redditUrl);
    if (postData.articleUrl) console.log('%c🔗 Article URL:', 'color:#ff4500; font-weight:bold;', postData.articleUrl);
    if (postData.text) console.log('Self-text length:', postData.text.length);
    if (postData.mediaUrls.length) console.log('Media:', postData.mediaUrls);
    console.groupEnd();

    // Simulate Network Request
    await new Promise(r => setTimeout(r, 1500));

    const mock = getMockResponse(postData);

    // Update UI
    noteEl.innerHTML = `
      <div style="display:flex; align-items:flex-start; gap:10px;">
        <div style="font-size:20px;">⛨</div>
        <div>
            <strong style="display:block; margin-bottom:4px;">
            This is clearly a satire post from The Onion.
            </strong>
            <span style="line-height:1.4;">
            ${mock.note}
            </span>
            <div style="margin-top:6px; font-size:0.85em; color:var(--color-neutral-content-weak, #666);">
                <strong>Sources:</strong> ${mock.sources.join(' • ')}
            </div>
        </div>
      </div>
    `;
})();