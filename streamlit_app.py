import streamlit as st
import asyncio
import sys
import os
import time
from datetime import datetime
import pandas as pd
from PIL import Image
import httpx
from urllib.parse import unquote

# Fix for Playwright on Windows: Force ProactorEventLoop
if sys.platform == 'win32':
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    except:
        pass

# Add current directory to path so backend can be imported
sys.path.append(os.path.abspath(os.path.curdir))

from backend.scrapers.search_all import search_all

# Page configuration
st.set_page_config(
    page_title="Quick Compare | Shop Smarter",
    page_icon="🛒",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS for Premium Look
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&display=swap');
    
    :root {
        --primary: #6366f1;
        --secondary: #a855f7;
        --accent: #f43f5e;
        --bg: #0f172a;
        --card-bg: rgba(30, 41, 59, 0.6);
        --text: #f8fafc;
        --text-muted: #94a3b8;
    }
    
    * {
        font-family: 'Plus Jakarta Sans', sans-serif;
    }
    
    /* Background Gradient */
    .stApp {
        background: radial-gradient(circle at top right, #1e1b4b, #0f172a);
        background-attachment: fixed;
    }
    
    /* Hero Section */
    .hero-container {
        padding: 4rem 2rem;
        text-align: center;
        background: transparent;
    }
    
    .hero-title {
        font-size: 4rem;
        font-weight: 800;
        letter-spacing: -0.05em;
        background: linear-gradient(135deg, #fff 0%, #94a3b8 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.5rem;
    }
    
    .hero-subtitle {
        font-size: 1.25rem;
        color: var(--text-muted);
        max-width: 600px;
        margin: 0 auto 2.5rem;
    }
    
    /* Search Bar Styling */
    .stTextInput > div > div > input {
        background: rgba(255, 255, 255, 0.05) !important;
        border: 1px solid rgba(255, 255, 255, 0.1) !important;
        border-radius: 12px !important;
        color: white !important;
        padding: 1rem 1.5rem !important;
        font-size: 1.1rem !important;
        transition: all 0.3s ease !important;
    }
    
    .stTextInput > div > div > input:focus {
        border-color: var(--primary) !important;
        box-shadow: 0 0 0 2px rgba(99, 102, 241, 0.2) !important;
        background: rgba(255, 255, 255, 0.08) !important;
    }
    
    /* Card Component */
    .product-card {
        background: var(--card-bg);
        backdrop-filter: blur(12px);
        -webkit-backdrop-filter: blur(12px);
        border: 1px solid rgba(255, 255, 255, 0.05);
        border-radius: 20px;
        padding: 1.25rem;
        height: 100%;
        display: flex;
        flex-direction: column;
        transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
        position: relative;
        overflow: hidden;
    }
    
    .product-card:hover {
        transform: translateY(-8px);
        border-color: rgba(99, 102, 241, 0.3);
        box-shadow: 0 20px 40px rgba(0, 0, 0, 0.4);
    }
    
    .product-image-container {
        width: 100%;
        height: 160px;
        border-radius: 12px;
        background: white;
        margin-bottom: 1rem;
        display: flex;
        align-items: center;
        justify-content: center;
        overflow: hidden;
        position: relative;
    }
    
    .product-image {
        max-width: 90%;
        max-height: 90%;
        object-fit: contain;
    }
    
    .platform-tag {
        position: absolute;
        top: 12px;
        right: 12px;
        padding: 4px 10px;
        border-radius: 8px;
        font-size: 0.7rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        z-index: 2;
    }
    
    .tag-blinkit { background: #ffeb3b; color: #000; }
    .tag-dmart { background: #4caf50; color: #fff; }
    .tag-jiomart { background: #007bff; color: #fff; }
    .tag-instamart { background: #ff5722; color: #fff; }
    
    .product-name {
        font-size: 1rem;
        font-weight: 600;
        color: white;
        margin-bottom: 0.5rem;
        line-height: 1.4;
        display: -webkit-box;
        -webkit-line-clamp: 2;
        -webkit-box-orient: vertical;
        overflow: hidden;
        height: 2.8rem;
    }
    
    .product-meta {
        font-size: 0.85rem;
        color: var(--text-muted);
        margin-bottom: 1rem;
    }
    
    .price-container {
        margin-top: auto;
        display: flex;
        align-items: baseline;
        gap: 0.5rem;
    }
    
    .price {
        font-size: 1.5rem;
        font-weight: 800;
        color: #fff;
    }
    
    .unit-price {
        font-size: 0.8rem;
        color: var(--text-muted);
    }
    
    .best-deal-badge {
        background: linear-gradient(90deg, #f43f5e, #fb7185);
        color: white;
        padding: 4px 12px;
        border-radius: 9999px;
        font-size: 0.75rem;
        font-weight: 700;
        display: inline-flex;
        align-items: center;
        gap: 4px;
        margin-bottom: 0.75rem;
    }
    
    .best-deal-glow {
        border-color: var(--accent) !important;
        box-shadow: 0 0 20px rgba(244, 63, 94, 0.3) !important;
    }

    /* Custom Sidebar */
    .css-1d391kg {
        background-color: #0f172a !important;
    }
</style>
""", unsafe_allow_html=True)

# Helper for image proxying
async def fetch_image(url):
    if not url: return None
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(url, headers={"User-Agent": "Mozilla/5.0"})
            if resp.status_code == 200:
                return resp.content
    except:
        pass
    return None

def get_platform_class(platform):
    p = platform.lower()
    if 'blinkit' in p: return 'tag-blinkit'
    if 'dmart' in p: return 'tag-dmart'
    if 'jiomart' in p: return 'tag-jiomart'
    if 'instamart' in p: return 'tag-instamart'
    return ''

# Header
st.markdown('<div class="hero-container">', unsafe_allow_html=True)
st.markdown('<h1 class="hero-title">Quick Compare</h1>', unsafe_allow_html=True)
st.markdown('<p class="hero-subtitle">Compare prices across Blinkit, DMart, JioMart, and Instamart in real-time. Find the best deals in seconds.</p>', unsafe_allow_html=True)
st.markdown('</div>', unsafe_allow_html=True)

# Sidebar
with st.sidebar:
    st.image("https://img.icons8.com/fluency/96/shopping-cart.png", width=80)
    st.title("Settings")
    
    pincode = st.text_input("📍 Delivery Pincode", value="380015")
    
    with st.expander("🌐 Advanced Location"):
        lat = st.number_input("Latitude", value=23.0225, format="%.4f")
        lng = st.number_input("Longitude", value=72.5714, format="%.4f")
    
    max_res = st.slider("Max Results per Platform", 10, 50, 20)
    headful = st.checkbox("Show Browser (Debug)", value=False)
    
    st.divider()
    st.markdown("### How it works")
    st.info("We search multiple grocery platforms simultaneously and group similar items to help you find the lowest price per unit.")

# Search Logic
col_search, _ = st.columns([2, 1])
with col_search:
    query = st.text_input("Search for products (e.g., 'Amul Milk', 'Maggi', 'Basmati Rice')", key="search_query")

if query:
    with st.spinner(f"🔍 Searching for '{query}' across all platforms..."):
        try:
            # Run the async search
            results = asyncio.run(search_all(
                query=query,
                pincode=pincode,
                lat=lat,
                lng=lng,
                max_results=max_res,
                headful=headful
            ))
            
            if results and results.get("all_results"):
                # Layout
                tab1, tab2, tab3 = st.tabs(["✨ Best Deals", "📊 Comparisons", "🔍 All Results"])
                
                # Best Deals Tab
                with tab1:
                    best_deals = results.get("best_deals", [])
                    if best_deals:
                        st.markdown("### 🔥 Top Savings Today")
                        best_deals_html = ""
                        for item in best_deals[:8]:
                            best_deals_html += f"""
<div style="width: 280px; margin: 10px;">
    <div class="product-card">
        <div class="best-deal-badge">🔥 {item.get('savings', 'Best Price')}</div>
        <div class="platform-tag {get_platform_class(item['platform'])}">{item['platform']}</div>
        <div class="product-image-container">
            <img src="{item.get('image_url', '')}" class="product-image" onerror="this.src='https://via.placeholder.com/150?text=No+Image'">
        </div>
        <div class="product-name">{item['name']}</div>
        <div class="product-meta">{item.get('quantity', '')}</div>
        <div class="price-container">
            <span class="price">₹{item.get('price', 0)}</span>
            <span class="unit-price">₹{item.get('unit_price', 0)}/g</span>
        </div>
        <a href="{item.get('link', '#')}" target="_blank" style="text-decoration:none; margin-top:1rem; display:block; text-align:center; background:var(--primary); color:white; padding:8px; border-radius:8px; font-weight:600; font-size:0.8rem;">View on {item['platform']}</a>
    </div>
</div>
""".strip().replace('\n', ' ')
                        st.markdown(f"""
<div style="display: flex; flex-wrap: wrap; justify-content: center; gap: 10px;">
{best_deals_html}
</div>
""", unsafe_allow_html=True)
                    else:
                        st.info("No multi-platform comparisons found to identify best deals yet. Try a broader search.")

                # Comparisons Tab
                with tab2:
                    comparisons = results.get("comparisons", [])
                    if comparisons:
                        for gid, group in enumerate(comparisons[:10]):
                            st.markdown(f"#### Comparison Group {gid+1}")
                            comp_html = ""
                            for item in group:
                                is_best = item.get("is_best_deal", False)
                                glow_class = "best-deal-glow" if is_best else ""
                                comp_html += f"""
<div style="width: 250px; margin: 10px;">
    <div class="product-card {glow_class}">
        {f'<div class="best-deal-badge">🏆 Best Choice</div>' if is_best else ''}
        <div class="platform-tag {get_platform_class(item['platform'])}">{item['platform']}</div>
        <div class="product-image-container">
            <img src="{item.get('image_url', '')}" class="product-image" onerror="this.src='https://via.placeholder.com/150?text=No+Image'">
        </div>
        <div class="product-name">{item['name']}</div>
        <div class="price-container">
            <span class="price">₹{item.get('price', 0)}</span>
        </div>
    </div>
</div>
""".strip().replace('\n', ' ')
                            st.markdown(f"""
<div style="display: flex; flex-wrap: wrap; gap: 10px;">
{comp_html}
</div>
""", unsafe_allow_html=True)
                            st.divider()
                    else:
                        st.info("No comparison groups found for this search.")

                # All Results Tab
                with tab3:
                    all_res = results.get("all_results", [])
                    
                    # Filtering in Tab 3
                    f_col1, f_col2 = st.columns([1, 3])
                    with f_col1:
                        platforms = ["All"] + list(results.get("by_platform", {}).keys())
                        p_filter = st.selectbox("Filter by Platform", platforms)
                    
                    filtered_res = all_res if p_filter == "All" else [r for r in all_res if r['platform'] == p_filter]
                    
                    st.write(f"Showing {len(filtered_res)} products")
                    
                    all_html = ""
                    for item in filtered_res:
                        all_html += f"""
<div style="width: 250px; margin: 10px;">
    <div class="product-card">
        <div class="platform-tag {get_platform_class(item['platform'])}">{item['platform']}</div>
        <div class="product-image-container">
            <img src="{item.get('image_url', '')}" class="product-image" onerror="this.src='https://via.placeholder.com/150?text=No+Image'">
        </div>
        <div class="product-name">{item['name']}</div>
        <div class="product-meta">{item.get('quantity', '')}</div>
        <div class="price-container">
            <span class="price">₹{item.get('price', 0)}</span>
        </div>
    </div>
</div>
""".strip().replace('\n', ' ')
                    st.markdown(f"""
<div style="display: flex; flex-wrap: wrap; gap: 10px;">
{all_html}
</div>
""", unsafe_allow_html=True)
                
            else:
                st.warning("No results found. Please try a different search term or check your pincode.")
                if results.get("errors"):
                    with st.expander("See technical errors"):
                        for err in results["errors"]:
                            st.error(f"{err['platform']}: {err['error']}")

        except Exception as e:
            st.error(f"An unexpected error occurred: {e}")
            import traceback
            st.code(traceback.format_exc())

else:
    # Empty state
    st.markdown("""
<div style="text-align:center; padding: 5rem 0; opacity: 0.5;">
    <img src="https://img.icons8.com/fluency/96/search.png" style="margin-bottom:1rem;">
    <p>Type something in the search bar to get started!</p>
</div>
""", unsafe_allow_html=True)

# Footer
st.divider()
st.markdown("""
<div style="text-align:center; color: #94a3b8; font-size: 0.8rem; padding: 2rem 0;">
    Quick Compare &copy; 2024 | Built with Streamlit and Playwright
</div>
""", unsafe_allow_html=True)
