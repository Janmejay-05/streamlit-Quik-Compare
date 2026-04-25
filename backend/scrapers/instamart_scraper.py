# backend/scrapers/instamart_scraper.py

from playwright.async_api import async_playwright
import asyncio
import random
import re
import os
import json



async def rand_delay(a=0.3, b=1.0):
    await asyncio.sleep(random.uniform(a, b))


STEALTH_JS = """
Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
window.chrome = { runtime: {} };
Object.defineProperty(navigator, 'plugins', { get: () => [1,2,3,4,5] });
Object.defineProperty(navigator, 'languages', { get: () => ['en-US','en'] });
delete navigator.__proto__.webdriver;
"""


def extract_quantity(text: str):
    if not text:
        return None, None, None
    
    text_lower = text.lower()
    
    patterns = [
        (r'(\d+(?:\.\d+)?)\s*kg', 'kg', 1000),
        (r'(\d+(?:\.\d+)?)\s*g(?:m|ram)?(?:\s|$|,)', 'g', 1),
        (r'(\d+(?:\.\d+)?)\s*l(?:itre|iter)?(?:\s|$|,)', 'l', 1000),
        (r'(\d+(?:\.\d+)?)\s*ml', 'ml', 1),
        (r'(\d+)\s*(?:pc|pcs|piece|pieces|pack)', 'pcs', None),
    ]
    
    for pattern, unit, multiplier in patterns:
        match = re.search(pattern, text_lower)
        if match:
            value = float(match.group(1))
            grams = value * multiplier if multiplier else None
            return value, unit, grams
    
    return None, None, None


def _lat_lng_to_address(lat: float, lng: float) -> str:
    """Return a city name based on approximate lat/lng coordinates."""
    # Common Indian city coordinates (approximate)
    cities = [
        (23.0225, 72.5714, "Ahmedabad, Gujarat"),
        (19.0760, 72.8777, "Mumbai, Maharashtra"),
        (28.6139, 77.2090, "New Delhi, Delhi"),
        (12.9716, 77.5946, "Bangalore, Karnataka"),
        (13.0827, 80.2707, "Chennai, Tamil Nadu"),
        (17.3850, 78.4867, "Hyderabad, Telangana"),
        (22.5726, 88.3639, "Kolkata, West Bengal"),
        (18.5204, 73.8567, "Pune, Maharashtra"),
        (26.9124, 75.7873, "Jaipur, Rajasthan"),
        (21.1702, 72.8311, "Surat, Gujarat"),
    ]
    
    best_city = "India"
    best_dist = float('inf')
    for city_lat, city_lng, city_name in cities:
        dist = abs(lat - city_lat) + abs(lng - city_lng)
        if dist < best_dist:
            best_dist = dist
            best_city = city_name
    
    return best_city


def _parse_products_from_text(body_text: str, max_results: int = 20):
    """
    Parse products from the visible page text.
    
    Instamart renders product cards with this text pattern:
        [X MINS]
        [Product Name]
        [Description (optional)]
        [Quantity e.g. "1 kg"]
        [Discount e.g. "33% OFF"]
        [Sale Price (number)]
        [Original Price (number, strikethrough)]
        
    Products may also have "Ad" label preceding them.
    """
    lines = [l.strip() for l in body_text.split("\n") if l.strip()]
    
    products = []
    i = 0
    while i < len(lines) and len(products) < max_results:
        line = lines[i]
        
        # Look for delivery time pattern "X MINS" - this starts a product block
        if re.match(r'^\d+\s*MINS?$', line, re.I):
            # Possibly an "Ad" label right before
            is_ad = (i > 0 and lines[i - 1].strip().lower() == "ad")
            
            # Skip the delivery time line
            j = i + 1
            
            # Next non-empty, non-delivery line should be the product name
            name = None
            description = None
            quantity = None
            discount = None
            sale_price = None
            original_price = None
            
            while j < len(lines) and j < i + 10:
                l = lines[j].strip()
                
                # Another delivery time means next product
                if re.match(r'^\d+\s*MINS?$', l, re.I):
                    break
                
                # Skip "Ad" labels
                if l.lower() == "ad":
                    j += 1
                    continue
                
                # Discount pattern
                if re.match(r'^\d+%\s*OFF$', l, re.I):
                    discount = l
                    j += 1
                    continue
                
                # Quantity pattern (e.g. "1 kg", "500 ml", "250 g")
                if re.match(r'^\d+(?:\.\d+)?\s*(kg|g|gm|ml|l|litre|ltr|pcs?|pack|piece)s?$', l, re.I):
                    quantity = l
                    j += 1
                    continue
                
                # Pure number — this is a price
                if re.match(r'^\d+(?:\.\d+)?$', l):
                    if sale_price is None:
                        sale_price = float(l)
                    elif original_price is None:
                        original_price = float(l)
                    j += 1
                    continue
                    
                # Price with ₹ symbol
                price_match = re.match(r'^₹\s*(\d+(?:\.\d+)?)', l)
                if price_match:
                    if sale_price is None:
                        sale_price = float(price_match.group(1))
                    elif original_price is None:
                        original_price = float(price_match.group(1))
                    j += 1
                    continue
                
                # Product name (first substantial text line)
                if name is None and len(l) > 3:
                    name = l
                    j += 1
                    continue
                
                # Description (second text line after name)
                if name and description is None and len(l) > 3:
                    description = l
                    j += 1
                    continue
                
                j += 1
            
            if name and sale_price is not None:
                products.append({
                    "name": name,
                    "price": sale_price,
                    "original_price": original_price,
                    "quantity": quantity,
                    "discount": discount,
                    "description": description,
                    "is_ad": is_ad,
                })
            
            # Move to the next product block
            i = j
        else:
            i += 1
    
    return products


async def _dismiss_overlays(page):
    """Try to close any blocking modals (login, location, etc)."""
    try:
        # Common close buttons or "X" icons
        selectors = [
            'div[class*="Close"], div[class*="close"]',
            'button:has-text("X"), span:has-text("X")',
            'div[role="button"]:has-text("Dismiss")',
            'svg[class*="close"]',
        ]
        for sel in selectors:
            btn = await page.query_selector(sel)
            if btn and await btn.is_visible():
                await btn.click()
                await asyncio.sleep(1)
    except:
        pass

async def _extract_products_via_dom(page, max_results: int):
    """Extract product data using DOM selectors for better reliability."""
    return await page.evaluate(f"""(limit) => {{
        const results = [];
        // Try multiple known container selectors for Instamart
        const cards = document.querySelectorAll('div[data-testid="item-card"], div._3p4LD, div[class*="ItemCard"]');
        
        for (const card of cards) {{
            if (results.length >= limit) break;
            
            const nameEl = card.querySelector('[data-testid="item-card-name"], [class*="itemName"], div:nth-child(2)');
            let priceEl = card.querySelector('[data-testid="item-card-price"], [class*="itemPrice"]');
            
            // Fallback for price if selector fails
            if (!priceEl) {
                const allElements = card.querySelectorAll('span, div, p');
                for (const el of allElements) {
                    if (el.innerText.includes('₹')) {
                        priceEl = el;
                        break;
                    }
                }
            }

            const imgEl = card.querySelector('img');
            const linkEl = card.closest('a') || card.querySelector('a');
            
            if (nameEl && priceEl) {{
                // Extract price as number
                const priceMatch = priceEl.innerText.match(/₹?\\s*(\\d+(?:\\.\\d+)?)/);
                const price = priceMatch ? parseFloat(priceMatch[1]) : null;
                
                if (price === null) continue;

                results.push({{
                    name: nameEl.innerText.trim(),
                    price: price,
                    image: imgEl ? (imgEl.src || imgEl.getAttribute('data-src') || imgEl.getAttribute('src') || '') : '',
                    link: linkEl ? linkEl.href : window.location.href,
                    quantity: card.innerText.match(/\\d+\\s*(?:kg|g|gm|ml|l|pcs?|pack)/i)?.[0] || ""
                }});
            }}
        }}
        return results;
    }}""", max_results)

async def search_instamart(
    query: str,
    lat: float = 23.0225,
    lng: float = 72.5714,
    max_results: int = 20,
    headful: bool = False,
    timeout: int = 60000
):
    """
    Search Swiggy Instamart for products using async Playwright.
    """
    print(f"[INSTAMART] Searching: {query}, lat={lat}, lng={lng}, headful={headful}")
    
    results = []
    address = _lat_lng_to_address(lat, lng)
    city = address.split(",")[0].strip()
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=not headful,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
                "--no-sandbox"
            ]
        )
        
        context = await browser.new_context(
            locale="en-IN",
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            viewport={"width": 1366, "height": 768},
            geolocation={"latitude": lat, "longitude": lng},
            permissions=["geolocation"],
            bypass_csp=True,
        )
        
        page = await context.new_page()
        await page.add_init_script(STEALTH_JS)
        
        try:
            # Step 1: Set location
            print("[INSTAMART] Setting location...")
            await page.goto("https://www.swiggy.com/instamart", wait_until="domcontentloaded", timeout=timeout)
            await rand_delay(2, 4)
            await _dismiss_overlays(page)
            
            # Set cookies and localStorage
            await page.evaluate(f"""() => {{
                localStorage.setItem('lat', '{lat}');
                localStorage.setItem('lng', '{lng}');
                localStorage.setItem('address', '{address}');
                localStorage.setItem('city', '{city}');
            }}""")
            
            # Step 2: Search
            search_url = f"https://www.swiggy.com/instamart/search?query={query}"
            print(f"[INSTAMART] Opening: {search_url}")
            await page.goto(search_url, wait_until="domcontentloaded", timeout=timeout)
            await rand_delay(3, 5)
            await _dismiss_overlays(page)
            
            # Step 3: Scroll to load images and more products
            print("[INSTAMART] Scrolling for images...")
            for _ in range(4):
                await page.evaluate("window.scrollBy(0, 800)")
                await rand_delay(0.5, 1)
            
            # Step 4: Extract
            parsed = await _extract_products_via_dom(page, max_results)
            print(f"[INSTAMART] Extracted {len(parsed)} products via DOM")
            
            for i, product in enumerate(parsed):
                results.append({
                    "id": f"instamart_{i}",
                    "name": product["name"],
                    "price": product["price"],
                    "quantity": product["quantity"],
                    "image": product["image"],
                    "link": product["link"],
                    "platform": "Instamart"
                })

        except Exception as e:
            print(f"[INSTAMART] Error: {e}")
            await _save_failure_dump(page)
        
        finally:
            await browser.close()
    
    print(f"[INSTAMART] Returning {len(results)} results")
    return results


async def _save_failure_dump(page):
    """Save screenshot and HTML dump for debugging."""
    try:
        screenshot_path = os.path.join(os.getcwd(), "instamart_failure_dump.png")
        await page.screenshot(path=screenshot_path, full_page=True)
        print(f"[INSTAMART] Saved failure screenshot to: {screenshot_path}")
        
        html_path = os.path.join(os.getcwd(), "instamart_failure_dump.html")
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(await page.content())
        print(f"[INSTAMART] Saved failure HTML to: {html_path}")
    except Exception as e:
        print(f"[INSTAMART] Error saving failure dump: {e}")
