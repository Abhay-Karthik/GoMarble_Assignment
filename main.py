from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from fastapi import Request
from fastapi.middleware.cors import CORSMiddleware
import asyncio
from urllib.parse import unquote
from playwright.async_api import async_playwright
import json
import pandas as pd
from bs4 import BeautifulSoup
import time
from typing import Dict, List, Tuple, Optional
import re
import openai
import logging
import os
from dotenv import load_dotenv
from pydantic import BaseModel

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="AI Review Scraper",
    description="API for scraping reviews from websites",
    version="1.0.0"
)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Initialize templates
templates = Jinja2Templates(directory="templates")

# Root route for serving the frontend
@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Get OpenAI API key from environment
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
if not OPENAI_API_KEY:
    raise EnvironmentError("OpenAI API key not found in environment variables")

openai.api_key = OPENAI_API_KEY

# Response Models
class Review(BaseModel):
    title: str
    text: str
    stars: Optional[float]
    user_name: str

class ReviewResponse(BaseModel):
    reviews_count: int
    review_list: List[Review]
    pages_with_unique_reviews: int
    url: str
    scrape_date: str

async def check_page_type(page) -> str:
    """Check the type of pagination used on the page."""
    patterns = {
        'infinite_scroll': [
            'window.addEventListener("scroll"',
            'IntersectionObserver',
            'infinite',
            'loadMore'
        ],
        'button': [
            '.next',
            '.Next',
            '[class*="pagination"] button',
            'button[class*="next"]',
            'a[class*="next"]'
        ],
        'numbered': [
            '.pagination',
            '[class*="pagination"]',
            'nav[role="navigation"]'
        ],
        'url': [
            'a[href*="page="]',
            'a[href*="/page/"]',
            'link[rel="next"]'
        ]
    }
    
    for ptype, selectors in patterns.items():
        for selector in selectors:
            try:
                if selector.startswith('.') or selector.startswith('['):
                    elements = await page.query_selector_all(selector)
                    if elements:
                        return ptype
                else:
                    content = await page.content()
                    if selector in content.lower():
                        return ptype
            except Exception as e:
                logger.error(f"Error checking page type: {str(e)}")
                continue
    
    return 'unknown'

async def scroll_and_load(page):
    """Handle dynamic content loading through scrolling and buttons."""
    try:
        current_height = 0
        for _ in range(3):
            try:
                await page.evaluate('''() => {
                    window.scrollTo({
                        top: document.body.scrollHeight,
                        behavior: 'smooth'
                    });
                }''')
                await page.wait_for_timeout(3000)
                
                new_height = await page.evaluate('document.body.scrollHeight')
                if new_height == current_height:
                    await page.wait_for_timeout(2000)
                    break
                current_height = new_height
            except Exception as scroll_error:
                logger.error(f"Scroll error: {str(scroll_error)}")
                await page.wait_for_timeout(2000)
                break
        
        await page.wait_for_timeout(2000)
        
        # Try clicking "Load More" buttons
        load_more_selectors = [
            'button:text-is("Show More")',
            'button:text-is("Load More")',
            'a:text-is("Show More")',
            'a:text-is("Load More")',
            '[class*="load-more"]',
            '[class*="show-more"]'
        ]
        
        for selector in load_more_selectors:
            try:
                while True:
                    more_btn = await page.query_selector(selector)
                    if not more_btn or not await more_btn.is_visible():
                        break
                    await more_btn.click()
                    await page.wait_for_timeout(3000)
            except Exception as e:
                continue
                
    except Exception as e:
        logger.error(f"Error in dynamic loading: {str(e)}")

async def handle_pagination(page, curr_page: int) -> bool:
    """Handle different types of pagination."""
    try:
        selectors = [
            f'[class*="pagination"] [aria-label="Page {curr_page + 1}"]',
            f'[class*="pagination"] a:text("{curr_page + 1}")',
            f'button:text("{curr_page + 1}")',
            f'a[href*="page={curr_page + 1}"]',
            '[class*="pagination"] [aria-label*="next"]',
            '[class*="pagination"] button:has-text(">")',
            '[class*="pagination"] a:has-text(">")',
            '.next a',
            'a[rel="next"]',
            '.pagination__next',
            '.pagination__item--next',
            '[class*="pagination"] button:not([disabled])',
            '[class*="pagination"] a:not([class*="disabled"])',
            'li.next a'
        ]

        for selector in selectors:
            try:
                try:
                    await page.wait_for_selector(selector, timeout=5000)
                except:
                    continue

                next_btn = await page.query_selector(selector)
                if next_btn and await next_btn.is_visible():
                    before_url = page.url
                    before_html = await page.content()
                    
                    await next_btn.scroll_into_view_if_needed()
                    await page.wait_for_timeout(1000)
                    
                    try:
                        await next_btn.click(timeout=5000)
                    except:
                        await page.evaluate('(element) => element.click()', next_btn)
                    
                    try:
                        await page.wait_for_load_state('networkidle', timeout=5000)
                    except:
                        await page.wait_for_timeout(2000)
                    
                    after_url = page.url
                    after_html = await page.content()
                    
                    if before_url != after_url or before_html != after_html:
                        return True
                
            except Exception as e:
                continue
        
        try:
            current_url = page.url            
            if 'page=' in current_url:
                next_url = re.sub(r'page=\d+', f'page={curr_page + 1}', current_url)
            else:
                separator = '&' if '?' in current_url else '?'
                next_url = f"{current_url}{separator}page={curr_page + 1}"
            
            response = await page.goto(next_url)
            if response and response.ok():
                await page.wait_for_timeout(2000)
                return True
        
        except Exception as e:
            pass
        
        return False
        
    except Exception as e:
        return False

async def grab_reviews(page) -> List[Dict]:
    """Get reviews from the current page."""
    reviews = await page.evaluate("""() => {
        function cleanText(text) {
            if (!text) return '';
            text = text.replace(/\\s+/g, ' ')
                      .replace(/\\r?\\n/g, ' ')
                      .trim();
            text = text.split(/(?:read more|show more|see more)/i)[0];
            
            const words = text.split(' ');
            let cleanedText = '';
            let lastPhrase = '';
            
            for (let i = 0; i < words.length; i++) {
                const currentPhrase = words.slice(i, i + 3).join(' ');
                if (cleanedText.includes(currentPhrase) && currentPhrase.split(' ').length > 2) {
                    continue;
                }
                if (cleanedText) {
                    cleanedText += ' ';
                }
                cleanedText += words[i];
                lastPhrase = currentPhrase;
            }
            
            return cleanedText.trim();
        }
        
        function getStars(element) {
            try {
                let stars = null;
                
                const star_elems = element.querySelectorAll(
                    '[class*="star-full"], [class*="star"][class*="filled"], .spr-icon-star, [class*="yotpo-star-full"], [class*="rating"] .full'
                );
                if (star_elems.length > 0) {
                    stars = star_elems.length;
                    if (stars >= 0 && stars <= 5) {
                        return stars;
                    }
                }

                const dataAttrs = ['data-rating', 'data-score', 'data-stars', 'data-value'];
                for (const attr of dataAttrs) {
                    const value = element.getAttribute(attr);
                    if (value && !isNaN(value)) {
                        stars = parseFloat(value);
                        if (stars >= 0 && stars <= 5) {
                            return stars;
                        }
                    }
                }
                
                const fullText = element.textContent || '';
                const patterns = [
                    /([1-5]([.,]\\d)?)\s*(?:star|\/\s*5|$)/i,
                    /Rated\s+([1-5]([.,]\\d)?)/i,
                    /Rating:\s*([1-5]([.,]\\d)?)/i,
                    /([★⭐✩✭]{1,5})/
                ];

                for (const pattern of patterns) {
                    const match = fullText.match(pattern);
                    if (match) {
                        if (match[1].includes('★') || match[1].includes('⭐')) {
                            stars = match[1].length;
                        } else {
                            stars = parseFloat(match[1].replace(',', '.'));
                        }
                        if (stars >= 0 && stars <= 5) {
                            return stars;
                        }
                    }
                }

                return null;
            } catch (error) {
                return null;
            }
        }

        function isValid(text) {
            if (!text) return false;
            
            const invalidPatterns = [
                /^reviews?$/i,
                /^write a review$/i,
                /^see reviews?$/i,
                /^\d+\s+reviews?$/i,
                /^verified\s+/i,
                /^published/i,
                /^see more/i,
                /^read more/i,
                /^showing/i,
                /^customer reviews?$/i
            ];
            
            if (invalidPatterns.some(pattern => pattern.test(text.trim()))) {
                return false;
            }
            
            return text.trim().split(/\\s+/).length >= 3;
        }

        const review_boxes = document.querySelectorAll(
            '.review-item, .review-content, [data-review-id], [class*="review-container"], [class*="review_container"], .jdgm-rev, .yotpo-review, .spr-review, .stamped-review, .loox-review, .reviewsio-review, .okendo-review, .trustpilot-review, [data-reviews-target], [class*="ReviewCard"], [class*="review-card"], [data-review], .okeReviews-review-item'
        );

        const seen = new Set();
        const found = [];

        Array.from(review_boxes).forEach(box => {
            const titleSelectors = [
                '[class*="review-title"]',
                '[class*="review_title"]',
                '[class*="ReviewTitle"]',
                '[class*="review-header"]',
                'h3', 'h4',
                '.review-title'
            ].join(',');

            const textSelectors = [
                '[class*="review-content"]',
                '[class*="review-body"]',
                '[class*="review_content"]',
                '[class*="ReviewContent"]',
                '[class*="review-text"]',
                '.jdgm-rev__body',
                '.yotpo-review-content',
                '.spr-review-content-body',
                '[class*="ReviewText"]',
                'p'
            ].join(',');

            const userSelectors = [
                '[class*="review-author"]',
                '[class*="reviewer-name"]',
                '[class*="author"]',
                '[class*="customer-name"]',
                '.jdgm-rev__author',
                '.yotpo-user-name',
                '.spr-review-header-byline',
                '[class*="ReviewAuthor"]'
            ].join(',');

            const title = cleanText(box.querySelector(titleSelectors)?.textContent);
            let text = cleanText(box.querySelector(textSelectors)?.textContent);

            if (!text) {
                const clone = box.cloneNode(true);
                const elementsToRemove = [
                    'button', 'input', 'select', 'option',
                    '[class*="more"]', '[class*="truncate"]',
                    '[class*="toggle"]', '[class*="expand"]',
                    'script', 'style', '[aria-hidden="true"]'
                ].join(',');
                
                Array.from(clone.querySelectorAll(elementsToRemove)).forEach(el => el.remove());
                text = cleanText(clone.textContent);
                
                if (text.length < 10) {
                    const mainContent = box.querySelector('[class*="content"], [class*="body"], [class*="text"]');
                    if (mainContent) {
                        text = cleanText(mainContent.textContent);
                    }
                }
            }

            const user_name = cleanText(box.querySelector(userSelectors)?.textContent) || 'Anonymous';
            const stars = getStars(box);

            if (isValid(text) && !seen.has(text)) {
                seen.add(text);
                found.push({title: title || "Review",
                    text: text,
                    stars: stars,
                    user_name: user_name
                });
            }
        });

        return found;
    }""")
    
    # Clean up and validate reviews
    cleaned = []
    for review in reviews:
        if review['text'] and len(review['text'].split()) >= 3:
            if review['stars'] is not None:
                try:
                    review['stars'] = float(review['stars'])
                    if not (0 <= review['stars'] <= 5):
                        review['stars'] = None
                except (ValueError, TypeError):
                    review['stars'] = None
            cleaned.append(review)
    
    # Get AI selectors
    html_content = await page.content()
    
    # Get AI selectors
    prompt = f"""Find CSS selectors for reviews in this HTML.
    Look for:
    1. Review container selectors
    2. Review text selectors
    3. Star rating selectors
    
    Return ONLY selectors like this:
    CONTAINERS: [selector1, selector2]
    CONTENT: [selector1, selector2]
    RATINGS: [selector1, selector2]
    """
    
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "You're an expert at finding CSS selectors for reviews."},
            {"role": "user", "content": prompt},
            {"role": "user", "content": html_content[:15000]}
        ],
        temperature=0.1
    )
    
    result = response['choices'][0]['message']['content']
    
    # Parse selectors
    containers = []
    content = []
    ratings = []
    
    current_list = None
    for line in result.split('\n'):
        if 'CONTAINERS:' in line:
            current_list = containers
            line = line.split('CONTAINERS:')[1]
        elif 'CONTENT:' in line:
            current_list = content
            line = line.split('CONTENT:')[1]
        elif 'RATINGS:' in line:
            current_list = ratings
            line = line.split('RATINGS:')[1]
            
        if current_list is not None:
            selectors = re.findall(r'[\'"]([^\'"]+)[\'"]', line)
            current_list.extend(selectors)

    # Try AI selectors
    ai_reviews = await page.evaluate("""(selectors) => {
        const found = [];
        const seen = new Set();
        
        for (const containerSelector of selectors.containers) {
            document.querySelectorAll(containerSelector).forEach(box => {
                for (const contentSelector of selectors.content) {
                    const textEl = box.querySelector(contentSelector);
                    if (!textEl) continue;
                    
                    const text = (textEl.textContent || '').trim();
                    if (!text || text.length < 10 || seen.has(text)) continue;
                    
                    let stars = null;
                    for (const ratingSelector of selectors.ratings) {
                        const ratingEl = box.querySelector(ratingSelector);
                        if (!ratingEl) continue;
                        
                        const match = ratingEl.textContent.match(/([1-5]([.,]\\d)?)/);
                        if (match) {
                            stars = parseFloat(match[1]);
                            break;
                        }
                    }
                    
                    seen.add(text);
                    found.push({
                        title: "Review",
                        text: text,
                        stars: stars,
                        user_name: "Anonymous"
                    });
                }
            });
        }
        
        return found;
    }""", {"containers": containers, "content": content, "ratings": ratings})
    
    # Combine reviews from both methods
    seen_text = set()
    all_reviews = []
    
    for review in cleaned:
        if review['text'] not in seen_text:
            seen_text.add(review['text'])
            all_reviews.append(review)

    for review in ai_reviews:
        if review['text'] not in seen_text:
            seen_text.add(review['text'])
            all_reviews.append(review)
    
    return all_reviews

from fastapi.responses import FileResponse
import tempfile
import json


async def scrape_site(url: str, max_count: int = 500) -> Dict:
    """Main function for scraping reviews."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        )
        page = await context.new_page()
        review_list = []
        successful_pages = 0
        
        try:
            logger.info("Loading page...")
            await page.goto(url, wait_until='domcontentloaded')
            await page.wait_for_timeout(2000)
            
            curr_page = 1
            
            while len(review_list) < max_count and curr_page <= 50:
                logger.info(f"Scraping page {curr_page}...")
                
                await scroll_and_load(page)
                
                new_batch = await grab_reviews(page)
                
                if new_batch:
                    initial_count = len(review_list)
                    
                    existing_texts = set(r['text'] for r in review_list)
                    unique_reviews = [r for r in new_batch if r['text'] not in existing_texts]
                    
                    # Convert reviews to match required format
                    formatted_reviews = [{
                    "title": review["title"],
                    "text": review["text"],      # Changed from "body" to "text"
                    "stars": review["stars"],    # Changed from "rating" to "stars"
                    "user_name": review["user_name"]  # Changed from "reviewer" to "user_name"
                    } for review in unique_reviews]
                    
                    review_list.extend(formatted_reviews)
                    
                    if len(review_list) > initial_count:
                        successful_pages += 1
                        logger.info(f"Found {len(unique_reviews)} new unique reviews on page {curr_page}")
                    else:
                        logger.info("No new unique reviews found. Stopping.")
                        break
                else:
                    logger.info("No reviews found on current page. Stopping.")
                    break
                
                if len(review_list) < max_count:
                    has_next = await handle_pagination(page, curr_page)
                    if not has_next:
                        logger.warning("No more pages available")
                        break
                    curr_page += 1
                else:
                    break
            
            result = {
                "reviews_count": len(review_list),
                "reviews": review_list
            }
            
            return result
            
        finally:
            await context.close()
            await browser.close()

@app.get("/api/reviews")
async def get_reviews(
    page: str = Query(..., description="URL to scrape reviews from"),
    max_count: int = Query(10000, ge=10, le=100000, description="Maximum number of reviews to scrape"),
    download: bool = Query(False, description="Download results as JSON file")
):
    try:
        url = unquote(page)
        logger.info(f"Scraping reviews from: {url}")
        result = await scrape_site(url, max_count)
        
        if download:
            # Create a temp file for the JSON
            with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as tmp:
                domain = url.split('/')[2].replace('www.', '')
                filename = f"{domain}_reviews.json"
                
                # Write formatted JSON to temp file
                json.dump(result, tmp, indent=2, ensure_ascii=False)
                
            # Return the file as a download
            return FileResponse(
                tmp.name,
                media_type='application/json',
                filename=filename
            )
        
        return result
    except Exception as e:
        logger.error(f"Error scraping reviews: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error scraping reviews: {str(e)}")