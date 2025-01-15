from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import asyncio
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
from urllib.parse import unquote

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
    title="Review Scraper API",
    description="API for scraping reviews from websites with LLM-enhanced extraction",
    version="1.0.0"
)

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

# Set OpenAI API key
openai.api_key = OPENAI_API_KEY

# Response Models
class Review(BaseModel):
    title: str
    body: str
    rating: Optional[float]
    reviewer: str

class ReviewResponse(BaseModel):
    reviews_count: int
    reviews: List[Review]
    pages_with_unique_reviews: int
    url: str
    scrape_date: str
async def detect_pagination_type(page) -> str:
    """Detect the type of pagination used on the page."""
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
                logger.error(f"Error detecting pagination type: {str(e)}")
                continue
    
    return 'unknown'
async def get_dynamic_selectors(html_content: str) -> Tuple[List[str], List[str], List[str]]:
    """Use LLM to identify dynamic CSS selectors for reviews."""
    prompt = f"""Analyze this HTML and identify CSS selectors for review elements.
    Focus on finding:
    1. Review container selectors that contain individual reviews
    2. Review content/body selectors
    3. Rating/stars selectors
    
    Return only the selectors in this exact format:
    CONTAINERS: [selector1, selector2, ...]
    CONTENT: [selector1, selector2, ...]
    RATINGS: [selector1, selector2, ...]
    """
    
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a web scraping expert that identifies CSS selectors for reviews."},
                {"role": "user", "content": prompt},
                {"role": "user", "content": html_content[:15000]}
            ],
            temperature=0.1
        )
        
        result = response['choices'][0]['message']['content']
        
        # Parse the response
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
        
        return containers, content, ratings
    except Exception as e:
        logger.error(f"Error getting dynamic selectors: {str(e)}")
        return [], [], []
async def extract_reviews_traditional(page) -> List[Dict]:
    """Extract reviews using traditional selectors."""
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
        
        function extractRating(element) {
            try {
                let rating = null;
                
                const stars = element.querySelectorAll(
                    '[class*="star-full"], [class*="star"][class*="filled"], .spr-icon-star, [class*="yotpo-star-full"], [class*="rating"] .full'
                );
                if (stars.length > 0) {
                    rating = stars.length;
                    if (rating >= 0 && rating <= 5) {
                        return rating;
                    }
                }

                const dataAttrs = ['data-rating', 'data-score', 'data-stars', 'data-value'];
                for (const attr of dataAttrs) {
                    const value = element.getAttribute(attr);
                    if (value && !isNaN(value)) {
                        rating = parseFloat(value);
                        if (rating >= 0 && rating <= 5) {
                            return rating;
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
                            rating = match[1].length;
                        } else {
                            rating = parseFloat(match[1].replace(',', '.'));
                        }
                        if (rating >= 0 && rating <= 5) {
                            return rating;
                        }
                    }
                }

                return null;
            } catch (error) {
                console.error('Error extracting rating:', error);
                return null;
            }
        }

        function isValidReview(text) {
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

        const reviewSelectors = [
            '.review-item',
            '.review-content',
            '[data-review-id]',
            '[class*="review-container"]',
            '[class*="review_container"]',
            '.jdgm-rev',
            '.yotpo-review',
            '.spr-review',
            '.stamped-review',
            '.loox-review',
            '.reviewsio-review',
            '.okendo-review',
            '.trustpilot-review',
            '[data-reviews-target]',
            '[class*="ReviewCard"]',
            '[class*="review-card"]',
            '[data-review]',
            '.okeReviews-review-item'
        ].join(',');

        let reviewElements = Array.from(document.querySelectorAll(reviewSelectors));
        
        if (reviewElements.length === 0) {
            reviewElements = Array.from(document.querySelectorAll('*')).filter(el => {
                const text = (el.textContent || '').toLowerCase();
                const classes = (el.className || '').toLowerCase();
                const id = (el.id || '').toLowerCase();
                return (text.includes('review') || classes.includes('review') || id.includes('review')) &&
                       el.children && el.children.length > 0 &&
                       !text.match(/^(write|see|read|view)\s+reviews?$/i);
            });
        }

        const seenContent = new Set();
        const reviews = [];

        reviewElements.forEach(element => {
            const titleSelectors = [
                '[class*="review-title"]',
                '[class*="review_title"]',
                '[class*="ReviewTitle"]',
                '[class*="review-header"]',
                'h3', 'h4',
                '.review-title'
            ].join(',');

            const bodySelectors = [
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

            const reviewerSelectors = [
                '[class*="review-author"]',
                '[class*="reviewer-name"]',
                '[class*="author"]',
                '[class*="customer-name"]',
                '.jdgm-rev__author',
                '.yotpo-user-name',
                '.spr-review-header-byline',
                '[class*="ReviewAuthor"]'
            ].join(',');

            const title = cleanText(element.querySelector(titleSelectors)?.textContent);
            let body = cleanText(element.querySelector(bodySelectors)?.textContent);

            if (!body) {
                const clone = element.cloneNode(true);
                const elementsToRemove = [
                    'button', 'input', 'select', 'option',
                    '[class*="more"]', '[class*="truncate"]',
                    '[class*="toggle"]', '[class*="expand"]',
                    'script', 'style', '[aria-hidden="true"]'
                ].join(',');
                
                Array.from(clone.querySelectorAll(elementsToRemove)).forEach(el => el.remove());
                body = cleanText(clone.textContent);
                
                if (body.length < 10) {
                    const mainContent = element.querySelector('[class*="content"], [class*="body"], [class*="text"]');
                    if (mainContent) {
                        body = cleanText(mainContent.textContent);
                    }
                }
            }

            const reviewer = cleanText(element.querySelector(reviewerSelectors)?.textContent) || 'Anonymous';
            const rating = extractRating(element);

            if (isValidReview(body) && !seenContent.has(body)) {
                seenContent.add(body);
                reviews.push({
                    title: title || "Review",
                    body: body,
                    rating: rating,
                    reviewer: reviewer
                });
            }
        });

        return reviews;
    }""")
    
    # Clean up and validate reviews
    cleaned_reviews = []
    for review in reviews:
        if review['body'] and len(review['body'].split()) >= 3:
            if review['rating'] is not None:
                try:
                    review['rating'] = float(review['rating'])
                    if not (0 <= review['rating'] <= 5):
                        review['rating'] = None
                except (ValueError, TypeError):
                    review['rating'] = None
            cleaned_reviews.append(review)
    
    return cleaned_reviews