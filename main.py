import os
import psycopg2
from playwright.sync_api import sync_playwright
import logging
import csv
import time
import random
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    logger.error("DATABASE_URL environment variable is not set")
    raise ValueError("DATABASE_URL must be configured in environment variables")

def save_to_supabase(data):
    if not data:
        logger.info("No data to save to Supabase")
        return
    try:
        conn = psycopg2.connect(DATABASE_URL, sslmode="require", options="-c search_path=public")
        logger.info("Connected to database successfully")
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS public.it_jobs (
                id SERIAL PRIMARY KEY,
                title TEXT,
                company TEXT,
                location TEXT,
                link TEXT,
                posted_date TEXT,
                scraped_date TIMESTAMP DEFAULT NOW()
            )
        """)
        logger.info("Ensured it_jobs table exists in public schema")
        inserted_count = 0
        for job in data:
            try:
                cur.execute("""
                    INSERT INTO public.it_jobs (title, company, location, link, posted_date)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (link) DO NOTHING
                """, (job.get("title", "N/A"), job.get("company", "N/A"), 
                      job.get("location", "N/A"), job.get("link", ""), 
                      job.get("posted_date", "N/A")))
                inserted_count += 1
            except psycopg2.Error as e:
                logger.warning(f"Failed to insert job {job.get('link', 'unknown')}: {e}")
        conn.commit()
        logger.info(f"Successfully saved {inserted_count} IT jobs to Supabase")
    except psycopg2.Error as e:
        logger.error(f"Database error during batch save: {e}")
        conn.rollback()
        raise
    finally:
        if 'cur' in locals():
            cur.close()
        if 'conn' in locals():
            conn.close()

def export_to_csv():
    try:
        conn = psycopg2.connect(DATABASE_URL, sslmode="require", options="-c search_path=public")
        cur = conn.cursor()
        cur.execute("SELECT * FROM public.it_jobs ORDER BY scraped_date DESC")
        rows = cur.fetchall()
        columns = ["id", "title", "company", "location", "link", "posted_date", "scraped_date"]
        with open("it_jobs.csv", "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(columns)
            writer.writerows(rows)
        logger.info("Exported IT jobs to it_jobs.csv")
    except psycopg2.Error as e:
        logger.error(f"CSV export error: {e}")
        raise
    finally:
        if 'cur' in locals():
            cur.close()
        if 'conn' in locals():
            conn.close()

def scrape_indeed_jobs():
    results = []
    max_pages = 5  # Limit to 5 pages to avoid excessive requests
    page_num = 0
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")  # Mimic real browser
            while page_num < max_pages:
                search_url = f"https://au.indeed.com/jobs?q=IT&l=Australia&start={page_num * 10}"
                logger.info(f"Navigating to {search_url}")
                page.goto(search_url, wait_until="networkidle", timeout=120000)  # Increased timeout
                logger.info("Waiting for dynamic content to load")
                page.wait_for_load_state("networkidle")
                page.wait_for_selector(".jobsearch-ResultsList", timeout=30000)  # Updated container selector

                # Try multiple possible job card containers
                job_selectors = [
                    ".jobsearch-ResultsList li",  # Common Indeed job list item
                    ".job_seen_beacon",           # Alternative job container
                    "article.job-card-container"  # Another possible structure
                ]
                jobs_found = False
                for selector in job_selectors:
                    jobs = page.query_selector_all(selector)
                    if jobs:
                        logger.info(f"Found jobs with selector: {selector}")
                        jobs_found = True
                        break
                if not jobs_found:
                    logger.warning("No job cards found with any selector")
                    break

                for job in jobs:
                    try:
                        # Flexible title extraction
                        title_elem = job.query_selector(".jobTitle a") or job.query_selector("h2 a")
                        title = title_elem.inner_text() if title_elem else "N/A"
                        # Flexible company extraction
                        company_elem = job.query_selector(".companyName") or job.query_selector("span.company")
                        company = company_elem.inner_text().strip() if company_elem else "N/A"
                        # Flexible location extraction
                        location_elem = job.query_selector(".companyLocation") or job.query_selector("div.location")
                        location = location_elem.inner_text().strip() if location_elem else "N/A"
                        # Flexible link extraction
                        link_elem = title_elem or job.query_selector("a[href]")
                        link = link_elem.get_attribute("href") if link_elem else ""
                        if link and not link.startswith("http"):
                            link = f"https://au.indeed.com{link}"
                        # Flexible date extraction
                        posted_date_elem = job.query_selector(".date") or job.query_selector("time")
                        posted_date = posted_date_elem.inner_text().strip() if posted_date_elem else "N/A"
                        results.append({
                            "title": title,
                            "company": company,
                            "location": location,
                            "link": link,
                            "posted_date": posted_date
                        })
                    except AttributeError as e:
                        logger.warning(f"Skipping incomplete job data: {e}")

                page_num += 1
                next_button = page.query_selector("a[aria-label='Next']") or page.query_selector("button[aria-label='Next']")
                if not next_button or not next_button.get_attribute("href"):
                    break
                time.sleep(random.uniform(2, 5))  # Rate limiting delay
            logger.info(f"Scraped {len(results)} IT jobs across {page_num} pages")
            browser.close()
            return results
    except Exception as e:
        logger.error(f"Scraping error: {e}")
        return results

if __name__ == "__main__":
    try:
        jobs = scrape_indeed_jobs()
        if jobs:
            save_to_supabase(jobs)
            export_to_csv()
        else:
            logger.info("No IT jobs found to save")
    except Exception as e:
        logger.error(f"Main execution failed: {e}")
        raise
