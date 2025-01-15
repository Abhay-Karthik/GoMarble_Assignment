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