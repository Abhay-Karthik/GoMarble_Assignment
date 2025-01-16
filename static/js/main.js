document.addEventListener('DOMContentLoaded', function() {
    const app = document.getElementById('root');
    
    // Create the main container
    const container = document.createElement('div');
    container.className = 'min-h-screen bg-gradient-to-br from-slate-50 to-slate-100';
    
    // Add header content
    container.innerHTML = `
        <div class="max-w-6xl mx-auto p-6">
            <div class="text-center mb-8 pt-8">
                <h1 class="text-4xl font-bold text-slate-800 mb-2">Review Scraper</h1>
                <p class="text-slate-600 mb-4">Extract and analyze customer reviews from any website</p>
                <div class="inline-flex items-center px-4 py-2 bg-white rounded-full shadow-sm border border-slate-200">
                    <span class="text-slate-600 text-sm">Developed by</span>
                    <span class="text-slate-800 font-semibold text-sm mx-2">Abhay Karthik D</span>
                    <span class="text-slate-400 mx-2">•</span>
                    <span class="text-slate-600 text-sm">Ramaiah Institute of Technology</span>
                </div>
            </div>

            <!-- Form Card -->
            <div class="mb-8 shadow-sm border border-slate-200 bg-white rounded-lg">
                <div class="border-b border-slate-100 p-6">
                    <h2 class="text-xl text-slate-800">Start Scraping</h2>
                    <p class="text-slate-500">Enter a URL to begin extracting reviews</p>
                </div>
                <div class="p-6">
                    <form id="scrapeForm" class="space-y-6">
                        <div class="space-y-2">
                            <label class="block text-sm font-medium text-slate-700">Website URL</label>
                            <div class="relative">
                                <input
                                    type="url"
                                    id="urlInput"
                                    class="w-full pl-10 pr-4 py-2 border border-slate-200 rounded-lg focus:ring-2 focus:ring-slate-500 focus:border-slate-500"
                                    required
                                    placeholder="https://example.com/product"
                                />
                            </div>
                        </div>
                        <button
                            type="submit"
                            id="submitButton"
                            class="w-full bg-slate-800 text-white p-3 rounded-lg hover:bg-slate-700 disabled:bg-slate-300 transition-colors duration-200 font-medium text-sm"
                        >
                            Start Scraping
                        </button>
                    </form>
                </div>
            </div>

            <!-- Results Container -->
            <div id="resultsContainer" class="space-y-8 hidden">
            </div>

            <!-- Error Alert -->
            <div id="errorAlert" class="mb-8 hidden">
            </div>
        </div>
    `;

    // Add the container to the page
    app.appendChild(container);

    // Handle form submission
    const form = document.getElementById('scrapeForm');
    const submitButton = document.getElementById('submitButton');
    const resultsContainer = document.getElementById('resultsContainer');
    const errorAlert = document.getElementById('errorAlert');

    form.addEventListener('submit', async function(e) {
        e.preventDefault();
        
        const urlInput = document.getElementById('urlInput');
        const url = urlInput.value;
        
        // Show loading state
        submitButton.disabled = true;
        submitButton.innerHTML = `
            <svg class="animate-spin -ml-1 mr-3 h-5 w-5 inline-block" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
            Scraping Reviews...
        `;
        
        try {
            const encodedUrl = encodeURIComponent(url);
            const response = await fetch(`/api/reviews?page=${encodedUrl}&max_reviews=10000`);
            
            if (!response.ok) {
                throw new Error('Failed to fetch reviews');
            }
            
            const data = await response.json();
            
            // Clear previous results
            resultsContainer.innerHTML = '';
            errorAlert.classList.add('hidden');
            
            // Create stats cards
            const statsHtml = `
                <div class="grid md:grid-cols-3 gap-6">
                    <div class="shadow-sm border border-slate-200 bg-white rounded-lg p-6">
                        <div class="flex items-center space-x-4">
                            <div class="p-3 bg-slate-100 rounded-lg">
                                <svg class="h-6 w-6 text-slate-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                                </svg>
                            </div>
                            <div>
                                <p class="text-sm font-medium text-slate-500">Total Reviews</p>
                                <p class="text-2xl font-bold text-slate-800">${data.reviews_count}</p>
                            </div>
                        </div>
                    </div>
                    <!-- Add similar cards for Pages Scraped and Average Rating -->
                </div>
            `;
            
            // Create reviews grid
            const reviewsHtml = `
                <div class="grid md:grid-cols-2 gap-6">
                    ${data.reviews.map(review => `
                        <div class="shadow-sm border border-slate-200 bg-white rounded-lg p-6">
                            <div class="flex justify-between items-start mb-4">
                                <div class="flex items-center space-x-3">
                                    <div class="w-8 h-8 rounded-full bg-slate-100 flex items-center justify-center">
                                        <span class="text-slate-600 font-medium">${review.reviewer[0].toUpperCase()}</span>
                                    </div>
                                    <div>
                                        <h3 class="font-medium text-slate-800">${review.reviewer}</h3>
                                        <p class="text-sm text-slate-500">${data.scrape_date.split(' ')[0]}</p>
                                    </div>
                                </div>
                                ${review.rating ? `
                                    <div class="flex items-center bg-slate-50 px-2 py-1 rounded border border-slate-200">
                                        <svg class="w-4 h-4 text-amber-500" fill="currentColor" viewBox="0 0 20 20">
                                            <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
                                        </svg>
                                        <span class="ml-1 text-sm font-medium text-slate-600">${review.rating}</span>
                                    </div>
                                ` : ''}
                            </div>
                            ${review.title !== "Review" ? `
                                <h4 class="font-semibold text-slate-800 mb-2">${review.title}</h4>
                            ` : ''}
                            <p class="text-slate-600 leading-relaxed">${review.body}</p>
                        </div>
                    `).join('')}
                </div>
            `;
            
            resultsContainer.innerHTML = statsHtml + reviewsHtml;
            resultsContainer.classList.remove('hidden');
            
        } catch (error) {
            errorAlert.innerHTML = `
                <div class="bg-red-50 border border-red-200 text-red-600 px-4 py-3 rounded relative">
                    <strong class="font-bold">Error!</strong>
                    <span class="block sm:inline"> ${error.message}</span>
                </div>
            `;
            errorAlert.classList.remove('hidden');
        } finally {
            submitButton.disabled = false;
            submitButton.innerHTML = 'Start Scraping';
        }
    });
});