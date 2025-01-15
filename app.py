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