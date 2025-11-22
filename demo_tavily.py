"""
Tavily MCP Tools Demonstration Script

This script demonstrates the four main Tavily capabilities:
1. Search - Search the web for real-time information
2. Extract - Extract and process content from specific web pages
3. Crawl - Crawl multiple pages from a website
4. Map - Map and discover the structure of a website

Note: You'll need to install tavily-python:
    pip install tavily-python

You'll also need a Tavily API key. Get one at: https://tavily.com
Set it as an environment variable: export TAVILY_API_KEY=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
"""

import os
import re
from typing import Optional, Dict, Tuple

try:
    from tavily import TavilyClient
except ImportError:
    print("Error: tavily-python not installed. Install it with: pip install tavily-python")
    exit(1)


# Initialize Tavily client
def get_tavily_client() -> Optional[TavilyClient]:
    """Initialize and return Tavily client if API key is available."""
    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        print("Warning: TAVILY_API_KEY environment variable not set.")
        print("Get your API key at: https://tavily.com")
        print("Then set it with: export TAVILY_API_KEY=your_key_here")
        return None
    return TavilyClient(api_key=api_key)


def demo_search(client: TavilyClient):
    """Demonstrate Tavily Search - Search the web for real-time information."""
    print("\n" + "="*80)
    print("DEMO 1: TAVILY SEARCH")
    print("="*80)
    print("Searching for information about the Reddit post topic...")
    
    query = "Find the Post Header and DescriptionZohran Mamdani Trump comments Reddit politics"
    
    try:
        response = client.search(
            query=query,
            search_depth="basic",  # or "advanced" for deeper search
            max_results=5,
            include_domains=["reddit.com"],  # Focus on Reddit
            exclude_domains=[],
            include_answer=True,  # Get AI-generated answer
            include_raw_content=False,
            include_images=False,
        )
        
        print(f"\n✓ Search completed! Found {len(response.get('results', []))} results")
        print(f"\nAI-Generated Answer:")
        print(f"{response.get('answer', 'No answer generated')}")
        
        print(f"\nTop Results:")
        for i, result in enumerate(response.get('results', [])[:3], 1):
            print(f"\n{i}. {result.get('title', 'No title')}")
            print(f"   URL: {result.get('url', 'No URL')}")
            print(f"   Content: {result.get('content', '')[:200]}...")
            
    except Exception as e:
        print(f"✗ Error during search: {e}")


def extract_reddit_post_info(client: TavilyClient, url: str) -> Dict[str, Optional[str]]:
    """
    Extract Reddit post title and associated link from a Reddit post URL.
    
    Returns:
        dict with keys: 'title', 'link', 'raw_content'
    """
    try:
        response = client.extract(
            urls=[url],
            extract_depth="advanced",
            format="markdown",
            include_images=False,
            include_favicon=False,
        )
        
        if not response or len(response) == 0:
            return {'title': None, 'link': None, 'raw_content': None}
        
        extracted = response[0]
        content = extracted.get('content', '')
        title = extracted.get('title', '')
        
        # Parse the content to find the post title and link
        # Reddit posts typically have the title as the first heading or in the metadata
        post_title = None
        post_link = None
        
        # Method 1: Try to get title from extracted title (often works)
        if title and 'reddit' not in title.lower():
            # If title doesn't contain "reddit", it's likely the post title
            post_title = title.strip()
        
        # Method 2: Parse markdown content for title (usually first # heading)
        if not post_title and content:
            # Look for first markdown heading
            heading_match = re.search(r'^#+\s+(.+)$', content, re.MULTILINE)
            if heading_match:
                post_title = heading_match.group(1).strip()
        
        # Method 3: Look for title in content patterns
        if not post_title and content:
            # Try to find title patterns like "Title: ..." or bold text at start
            patterns = [
                r'^#\s+(.+?)(?:\n|$)',
                r'\*\*(.+?)\*\*',  # Bold text
                r'^(.+?)\n[-=]{3,}',  # Title followed by separator
            ]
            for pattern in patterns:
                match = re.search(pattern, content, re.MULTILINE | re.DOTALL)
                if match:
                    candidate = match.group(1).strip()
                    # Filter out common non-title patterns
                    if len(candidate) > 10 and len(candidate) < 200:
                        post_title = candidate
                        break
        
        # Extract links from content
        # Look for URLs that are NOT reddit.com links
        url_pattern = r'https?://[^\s\)]+'
        all_urls = re.findall(url_pattern, content)
        
        # Filter out Reddit URLs and common Reddit domains
        reddit_domains = ['reddit.com', 'redd.it', 'i.redd.it', 'preview.redd.it']
        external_links = [
            url for url in all_urls 
            if not any(domain in url.lower() for domain in reddit_domains)
        ]
        
        # Take the first external link (usually the post's source link)
        if external_links:
            post_link = external_links[0]
            # Clean up URL (remove trailing punctuation)
            post_link = re.sub(r'[.,;:!?]+$', '', post_link)
        
        return {
            'title': post_title,
            'link': post_link,
            'raw_content': content[:1000] if content else None  # First 1000 chars for debugging
        }
        
    except Exception as e:
        print(f"Error extracting Reddit post info: {e}")
        return {'title': None, 'link': None, 'raw_content': None}


def demo_extract(client: TavilyClient, url: str):
    """Demonstrate Tavily Extract - Extract and process content from specific web pages."""
    print("\n" + "="*80)
    print("DEMO 2: TAVILY EXTRACT")
    print("="*80)
    print(f"Extracting content from: {url}")
    
    # Special handling for Reddit posts
    if 'reddit.com' in url and '/comments/' in url:
        print("\n🔍 Detected Reddit post - Extracting title and associated link...")
        post_info = extract_reddit_post_info(client, url)
        
        print(f"\n✓ Extraction completed!")
        print("\n" + "-" * 80)
        print("REDDIT POST INFORMATION:")
        print("-" * 80)
        
        if post_info['title']:
            print(f"\n📰 Post Title:")
            print(f"   {post_info['title']}")
        else:
            print(f"\n⚠️  Post Title: Not found")
        
        if post_info['link']:
            print(f"\n🔗 Associated Link:")
            print(f"   {post_info['link']}")
        else:
            print(f"\n⚠️  Associated Link: Not found")
        
        print("\n" + "-" * 80)
        
        # Also show full extraction for comparison
        print("\nFull extraction details:")
        try:
            response = client.extract(
                urls=[url],
                extract_depth="advanced",
                format="markdown",
                include_images=False,
                include_favicon=False,
            )
            
            if response and len(response) > 0:
                extracted = response[0]
                print(f"Extracted Title: {extracted.get('title', 'No title')}")
                print(f"Content Length: {len(extracted.get('content', ''))} characters")
        except Exception as e:
            print(f"Error getting full extraction: {e}")
        
        return
    
    # Standard extraction for non-Reddit URLs
    try:
        response = client.extract(
            urls=[url],
            extract_depth="advanced",
            format="markdown",
            include_images=False,
            include_favicon=False,
        )
        
        print(f"\n✓ Extraction completed!")
        
        if response and len(response) > 0:
            extracted = response[0]
            print(f"\nTitle: {extracted.get('title', 'No title')}")
            print(f"URL: {extracted.get('url', 'No URL')}")
            print(f"Content Length: {len(extracted.get('content', ''))} characters")
            
            # Show first 500 characters
            content = extracted.get('content', '')
            print(f"\nFirst 500 characters of extracted content:")
            print("-" * 80)
            print(content[:500])
            if len(content) > 500:
                print("...")
            print("-" * 80)
        else:
            print("No content extracted.")
            
    except Exception as e:
        print(f"✗ Error during extraction: {e}")


def demo_crawl(client: TavilyClient, base_url: str):
    """Demonstrate Tavily Crawl - Crawl multiple pages from a website."""
    print("\n" + "="*80)
    print("DEMO 3: TAVILY CRAWL")
    print("="*80)
    print(f"Crawling website starting from: {base_url}")
    print("This will explore multiple pages on the site...")
    
    try:
        response = client.crawl(
            url=base_url,
            max_depth=2,  # How deep to crawl (1-3 recommended)
            max_breadth=10,  # Max links per page
            limit=20,  # Total pages to crawl
            extract_depth="basic",
            format="markdown",
            include_images=False,
            instructions="Extract Reddit post content, comments, and metadata",
        )
        
        print(f"\n✓ Crawl completed! Processed {len(response)} pages")
        
        print(f"\nCrawled Pages:")
        for i, page in enumerate(response[:5], 1):  # Show first 5 pages
            print(f"\n{i}. {page.get('title', 'No title')}")
            print(f"   URL: {page.get('url', 'No URL')}")
            print(f"   Content preview: {page.get('content', '')[:150]}...")
            
        if len(response) > 5:
            print(f"\n... and {len(response) - 5} more pages")
            
    except Exception as e:
        print(f"✗ Error during crawl: {e}")


def demo_map(client: TavilyClient, base_url: str):
    """Demonstrate Tavily Map - Map and discover the structure of a website."""
    print("\n" + "="*80)
    print("DEMO 4: TAVILY MAP")
    print("="*80)
    print(f"Mapping website structure starting from: {base_url}")
    print("This will discover all URLs and pages without extracting full content...")
    
    try:
        response = client.map(
            url=base_url,
            max_depth=2,
            max_breadth=15,
            limit=30,
            instructions="Find all Reddit post pages, comment threads, and related content",
        )
        
        print(f"\n✓ Mapping completed! Discovered {len(response)} URLs")
        
        print(f"\nDiscovered URLs:")
        for i, url_info in enumerate(response[:10], 1):  # Show first 10 URLs
            url = url_info.get('url', 'No URL')
            title = url_info.get('title', 'No title')
            print(f"{i}. {title}")
            print(f"   {url}")
            
        if len(response) > 10:
            print(f"\n... and {len(response) - 10} more URLs")
            
        # Group by path pattern
        print(f"\nURL Patterns Discovered:")
        patterns = {}
        for url_info in response:
            url = url_info.get('url', '')
            if '/r/' in url:
                # Extract subreddit pattern
                parts = url.split('/r/')
                if len(parts) > 1:
                    pattern = '/r/' + parts[1].split('/')[0]
                    patterns[pattern] = patterns.get(pattern, 0) + 1
        
        for pattern, count in sorted(patterns.items(), key=lambda x: x[1], reverse=True)[:5]:
            print(f"  {pattern}: {count} pages")
            
    except Exception as e:
        print(f"✗ Error during mapping: {e}")


def get_reddit_post_title_and_link(client: TavilyClient, reddit_url: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Utility function to extract just the title and link from a Reddit post.
    
    Args:
        client: TavilyClient instance
        reddit_url: URL of the Reddit post
        
    Returns:
        Tuple of (title, link) or (None, None) if extraction fails
    """
    post_info = extract_reddit_post_info(client, reddit_url)
    return post_info['title'], post_info['link']


def main():
    """Main function to run all demonstrations."""
    print("="*80)
    print("TAVILY MCP TOOLS DEMONSTRATION")
    print("="*80)
    print("\nThis script demonstrates four Tavily capabilities:")
    print("1. Search - Search the web for real-time information")
    print("2. Extract - Extract content from specific web pages")
    print("3. Crawl - Crawl multiple pages from a website")
    print("4. Map - Map and discover the structure of a website")
    
    # The Reddit URL to use
    reddit_url = "https://www.reddit.com/r/politics/comments/1p3ap5k/zohran_mamdani_refuses_to_take_back_calling_trump/"
    base_url = "https://www.reddit.com/r/politics"
    
    # Initialize client
    client = get_tavily_client()
    if not client:
        print("\nCannot proceed without Tavily API key.")
        return
    
    print(f"\nUsing Reddit URL: {reddit_url}")
    print(f"Base URL for crawl/map: {base_url}")
    
    # Run all demonstrations
    try:
        # Demo 1: Search
        demo_search(client)
        
        # Demo 2: Extract (with special Reddit post handling)
        print("\n" + "="*80)
        print("DEMO 2A: REDDIT POST EXTRACTION (Title + Link)")
        print("="*80)
        print(f"Extracting title and link from: {reddit_url}")
        title, link = get_reddit_post_title_and_link(client, reddit_url)
        print(f"\n✓ Extraction Results:")
        print(f"   Title: {title if title else 'Not found'}")
        print(f"   Link: {link if link else 'Not found'}")
        
        # Demo 2: Full Extract
        demo_extract(client, reddit_url)
        
        # Demo 3: Crawl (using base URL to avoid crawling entire Reddit)
        demo_crawl(client, base_url)
        
        # Demo 4: Map
        demo_map(client, base_url)
        
        print("\n" + "="*80)
        print("ALL DEMONSTRATIONS COMPLETED!")
        print("="*80)
        print("\nSummary:")
        print("✓ Search: Found web results about the topic")
        print("✓ Extract: Extracted title and link from Reddit post")
        print("✓ Crawl: Explored multiple pages on the subreddit")
        print("✓ Map: Discovered the structure and URLs of the subreddit")
        
    except KeyboardInterrupt:
        print("\n\nInterrupted by user.")
    except Exception as e:
        print(f"\n\nUnexpected error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()

