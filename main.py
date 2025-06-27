import os
import psycopg2
from playwright.sync_api import sync_playwright
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Get DATABASE_URL from environment variables
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    logger.error("DATABASE_URL environment variable is not set")
    raise ValueError("DATABASE_URL must be configured in environment variables")

def save_to_postgres(data):
    """
    Save job data to the PostgreSQL database using the DATABASE_URL connection string.
    """
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                id SERIAL PRIMARY KEY,
                title TEXT,
                company TEXT,
                location TEXT,
                link TEXT,
                posted_on TIMESTAMP DEFAULT NOW()
            );
        """)
        for job in data:
            cur.execute("""
                INSERT INTO jobs (title, company, location, link)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (link) DO NOTHING
            """, (job["title"], job["company"], job["location"], job["link"]))
        conn.commit()
        logger.info(f"Successfully saved {len(data)} jobs to the database")
    except psycopg2.Error as e:
        logger.error(f"Database error: {e}")
        conn.rollback()
        raise
    finally:
        if 'cur' in locals():
            cur.close()
        if 'conn' in locals():
            conn.close()

def scrape_jobs():
    """
    Scrape job listings from a website using Playwright.
    """
    results = []
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto("https://www.seek.com.au/jobs", wait_until="networkidle")
            jobs = page.query_selector_all(".job-listing")
            for job in jobs:
                try:
                    title = job.query_selector("h2").inner_text()
                    company = job.query_selector(".company").inner_text()
                    location = job.query_selector(".location").inner_text()
                    link = job.query_selector("a").get_attribute("href") or ""
                    if link and not link.startswith("http"):
                        link = page.url + link
                    results.append({"title": title, "company": company, "location": location, "link": link})
                except AttributeError as e:
                    logger.warning(f"Skipping incomplete job data: {e}")
            browser.close()
        logger.info(f"Scraped {len(results)} jobs")
        return results
    except Exception as e:
        logger.error(f"Scraping error: {e}")
        raise

if __name__ == "__main__":
    try:
        jobs = scrape_jobs()
        if jobs:
            save_to_postgres(jobs)
        else:
            logger.info("No jobs found to save")
    except Exception as e:
        logger.error(f"Main execution failed: {e}")
        raise
