# GoMarble Review Scraper

## 🚀 Project Overview

GoMarble Review Scraper is an advanced web application designed to extract and analyze customer reviews from various websites using AI-powered techniques. Built as an academic project, this tool demonstrates web scraping, AI integration, and full-stack development skills.

## ✨ Proven Compatibility

The scraper has been successfully tested on multiple websites, demonstrating robust review extraction capabilities:

### Verified Working Websites
- [Bhumi](https://bhumi.com.au/)
  - Successful multi-page review scraping
  - Detailed review analysis
  - Consistent data extraction

### Key Compatibility Features
- Handles dynamic content loading
- Extracts reviews from various website structures
- Works with both single-page and paginated review sections

## 🌐 Key Features

- 🤖 AI-Enhanced Review Extraction
- 📊 Comprehensive Review Analysis
  - Total review count
  - Pages scraped
  - Average rating calculation
- 📥 JSON Export functionality
- 💻 Responsive, modern UI
- 🔍 Multi-Website Support

## 🌟 Website Compatibility Notes

### Tips for Best Results
- Ensure the website has publicly accessible reviews
- Works best with websites using standard review display methods
- Recommended for e-commerce, product, and service review pages

### Limitations
- Some websites may have anti-scraping measures
- Complex JavaScript-heavy sites might require additional configuration
- Always respect website terms of service

## 🔍 How It Works

The scraper uses advanced techniques to:
- Navigate through review pages
- Extract review content intelligently
- Handle various website structures
- Apply AI-powered content analysis

### Recommended Websites
- E-commerce platforms
- Product review sites
- Service review pages
- Consumer goods websites


## 🛠 Technology Stack

- **Backend**: 
  - FastAPI
  - Playwright
  - OpenAI API
- **Frontend**: 
  - Vanilla JavaScript
  - Tailwind CSS
- **Web Scraping**: 
  - Dynamic content handling
  - Intelligent review extraction

## 📋 Prerequisites

- Python 3.8+
- Node.js 14+
- pip (Python Package Manager)
- npm (Node Package Manager)
- OpenAI API Key

## 🔧 Installation Guide

### 1. Clone the Repository
```bash
git clone [your-repository-url]
cd GoMarble_Assignment
```

### 2. Set Up Python Virtual Environment
```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# On macOS/Linux:
source venv/bin/activate
# On Windows:
venv\Scripts\activate
```

### 3. Install Python Dependencies
```bash
pip install -r requirements.txt

# Install Playwright browsers
playwright install
```

### 4. Set Up Frontend
```bash
# Initialize npm project
npm init -y

# Install Tailwind CSS
npm install tailwindcss

# Build CSS
npm run build-css
```

### 5. Configure Environment Variables
Create a `.env` file in the project root:
```
OPENAI_API_KEY=your_openai_api_key_here
```

## 🚀 Running the Application

### Development Mode
```bash
# Ensure virtual environment is activated
uvicorn main:app --reload
```

### Access the Application
Open `http://localhost:8000` in your web browser

## 🐳 Docker Deployment

### Build and Run
```bash
# Build the container
docker-compose build

# Start the container
docker-compose up
```

## 📂 Project Structure
```
GoMarble_Assignment/
├── static/
│   ├── css/
│   │   ├── input.css
│   │   └── style.css
│   └── js/
│       └── main.js
├── templates/
│   └── index.html
├── main.py
├── package.json
├── tailwind.config.js
└── .env
```

## ⚠️ Limitations & Considerations

- Review extraction depends on website structure
- Maximum of 10,000 reviews per scrape
- Requires websites with public reviews
- OpenAI API usage may incur costs

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Open a Pull Request

## 📄 License

Distributed under the MIT License.

## 👥 Project Team

**Developed by:**
- Abhay Karthik D
- Ramaiah Institute of Technology

## 📞 Contact

- Email: abhaykarthik123@gmail.com
- website: https://abhay-karthik.github.io/website/

