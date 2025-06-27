import os
import psycopg2
from playwright.sync_api import sync_playwright
import logging
import csv
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
        # Explicitly create table in public schema
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
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            search_url = "https://au.indeed.com/jobs?q=IT&l=Australia"
            page.goto(search_url, wait_until="networkidle", timeout=60000)
            logger.info(f"Scraping jobs from {search_url}")

            jobs = page.query_selector_all("div.jobsearch-SerpJobCard")
            for job in jobs:
                try:
                    title_elem = job.query_selector("h2.jobTitle a")
                    title = title_elem.inner_text() if title_elem else "N/A"
                    company_elem = job.query_selector("span.company")
                    company = company_elem.inner_text().strip() if company_elem else "N/A"
                    location_elem = job.query_selector("div.companyLocation")
                    location = location_elem.inner_text().strip() if location_elem else "N/A"
                    link_elem = title_elem
                    link = link_elem.get_attribute("href") if link_elem else ""
                    if link and not link.startswith("http"):
                        link = f"https://au.indeed.com{link}"
                    posted_date_elem = job.query_selector("span.date")
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
            logger.info(f"Scraped {len(results)} IT jobs")
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
