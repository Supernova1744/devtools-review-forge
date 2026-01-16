import json
import time
import pandas as pd
import html
import traceback
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By


class CapterraScraper:
    def __init__(self, browser_executable_path):
        if browser_executable_path is None:
            print("❌ No browser executable path provided. Please provide a path to the browser executable.")
            exit(1)
        options = uc.ChromeOptions()
        options.add_argument("--no-first-run")
        options.add_argument("--force-device-scale-factor=1")
        options.add_argument("--start-maximized")

        print("🚀 Initializing Browser (this may take a moment)...")
        try:
            self.driver = uc.Chrome(browser_executable_path=browser_executable_path, options=options)
        except Exception as e:
            print(f"❌ Error initializing browser: {e}")
            traceback.print_exc()
            exit(1)

        print("✅ Browser Initialized!")
        self.data = []

    def run(self, target_url, output_file, max_pages=15):
        try:
            print(f"🔗 Navigating to: {target_url}")
            self.driver.get(target_url)

            print("\n" + "!"*60)
            print("🛑 ACTION REQUIRED: Check the Chrome window!")
            print("1. If you see a 'Verify you are human' checkbox, CLICK IT.")
            print("2. Wait for the reviews (stars and text) to actually load.")
            print("!"*60 + "\n")
            input("👉 Once the page is fully loaded, press ENTER here to scrape... ")

            page_number = 1

            while page_number <= max_pages:
                print(f"\n--- Scraping Page {page_number} ---")
                
                # Scroll down to ensure dynamic content loads
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                
                self.scrape_current_page()
                # Try to go to the next page
                if not self.go_to_next_page():
                    print("🛑 No more pages found or reached end.")
                    break
                
                page_number += 1
                time.sleep(2)

            self.save(output_file)

        except Exception as e:
            print(f"❌ Error: {e}")
            traceback.print_exc()
        finally:
            print("👋 Closing browser...")
            try:
                self.driver.quit()
                # Suppress double-quit in __del__
                self.driver.quit = lambda: None
            except Exception:
                pass



    def scrape_current_page(self):
        print("🔍 Scanning for review cards (DOM-based)...")
        
        # Strategy: Find cards by looking for the Reviewer Profile Picture which is a consistent anchor
        cards = self.driver.find_elements(By.XPATH, "//div[descendant::img[@data-testid='reviewer-profile-pic']]")
        
        if not cards:
            # Fallback: Try a broader search if the profile pic attribute changes
            # Look for the container of the stars
            cards = self.driver.find_elements(By.XPATH, "//div[descendant::div[@data-testid='rating']]")

        print(f"   > Found {len(cards)} review cards.")

        for card in cards:
            try:
                # 1. Rating
                # Try to find the star rating number
                try:
                    rating_el = card.find_element(By.XPATH, ".//div[@data-testid='rating']/following-sibling::span")
                    rating = rating_el.text.strip()
                except:
                    rating = "N/A"

                # 2. General Comment
                # Usually in a separate div with a paragraph, before Pros/Cons
                # We leverage the '!mt-4' class seen in the snippet or just look for the first free-standing paragraph
                general_text = ""
                try:
                    # Try specific class first (from user snippet)
                    gen_el = card.find_elements(By.XPATH, ".//div[contains(@class, '!mt-4')]//p")
                    if gen_el:
                        general_text = gen_el[0].text.strip()
                    else:
                        # Fallback: Find P tags that are NOT inside the Pros/Cons specialized blocks
                        # This is harder to do purely with clean XPATH in one shot, so we iterate
                        all_ps = card.find_elements(By.TAG_NAME, "p")
                        for p in all_ps:
                            # Heuristic: General comments are usually the first ones and plain text
                            txt = p.text.strip()
                            if len(txt) > 20 and "Pros" not in p.xpath("..").get_attribute("innerText") \
                                             and "Cons" not in p.xpath("..").get_attribute("innerText"):
                                general_text = txt
                                break
                except Exception as e:
                    pass

                # 3. Pros
                pros_text = ""
                try:
                    # Look for "Pros" text in a span/header, then get the paragraph following it or inside it
                    # User snippet: <span ...>Pros</span> <p>...</p> (inside a shared div or sibling)
                    # We look for the "Pros" label, then find the 'p' sibling or child of parent
                    pros_el = card.find_elements(By.XPATH, ".//span[contains(., 'Pros')]/following-sibling::p | .//span[contains(., 'Pros')]/../p")
                    if pros_el:
                        pros_text = pros_el[0].text.strip()
                except: pass

                # 4. Cons
                cons_text = ""
                try:
                    # Same logic for Cons
                    cons_el = card.find_elements(By.XPATH, ".//span[contains(., 'Cons')]/following-sibling::p | .//span[contains(., 'Cons')]/../p")
                    if cons_el:
                        cons_text = cons_el[0].text.strip()
                except: pass

                # Only add if we found *something*
                if general_text or pros_text or cons_text:
                    self.data.append({
                        "tool": "VS Code",
                        "source": "Capterra",
                        "general": general_text,
                        "pros": pros_text,
                        "cons": cons_text,
                        "rating": rating
                    })
                    
            except Exception as e:
                print(f"⚠️ Error parsing a card: {e}")
                continue

    def go_to_next_page(self):
        try:
            # Selector based on user provided HTML:
            # Look for the 'chevron-right' icon which indicates the Next button
            # <i role="img" aria-label="chevron-right" ...>
            next_buttons = self.driver.find_elements(By.XPATH, "//i[@aria-label='chevron-right'] | //i[contains(@class, 'icon-chevron-right')]")
            
            if next_buttons:
                # Click the last one found (usually bottom pagination)
                btn = next_buttons[-1]
                print("➡️ Found 'Next' button (chevron-right). Clicking...")
                
                # Scroll into view just in case
                self.driver.execute_script("arguments[0].scrollIntoView(true);", btn)
                time.sleep(1)
                
                # Javascript click is often more reliable for obscurely covered elements
                # We try clicking the icon, effectively clicking the parent anchor
                self.driver.execute_script("arguments[0].click();", btn)
                return True
            
            # Fallback: Check for traditional "Next" text just in case layout changes
            print("⚠️ Chevron not found. Checking for 'Next' text...")
            fallback_btns = self.driver.find_elements(By.XPATH, "//button[contains(., 'Next')] | //a[contains(., 'Next')]")
            if fallback_btns:
                self.driver.execute_script("arguments[0].click();", fallback_btns[-1])
                return True

            print("🚫 'Next' button not found.")
            return False
            
        except Exception as e:
            print(f"⚠️ Failed to go to next page: {e}")
            return False

    def save(self, output_file):
        if not self.data:
            print("❌ No data found. Did Cloudflare block the page?")
            return

        df = pd.DataFrame(self.data)
        
        # Remove duplicates based on the content (combination of reviews)
        # using a lambda to handle potentially empty fields
        df['combined_key'] = df['general'] + df['pros'] + df['cons']
        df.drop_duplicates(subset=['combined_key'], inplace=True)
        df.drop(columns=['combined_key'], inplace=True)
        
        # Save to CSV
        df.to_csv(output_file, index=False, encoding='utf-8-sig') # utf-8-sig for Excel compatibility
        print(f"\n✅ SUCCESS: Saved {len(df)} reviews to '{output_file}'")
        if not df.empty:
            print(df[['rating', 'general', 'pros', 'cons']].head())

if __name__ == "__main__":
    browser_executable_path = None
    TARGET_URL = "https://www.capterra.com/p/186634/Visual-Studio-Code/reviews/"
    OUTPUT_FILE = "data/real_reviews_capterra.csv"

    scraper = CapterraScraper(browser_executable_path)
    scraper.run(TARGET_URL, OUTPUT_FILE)