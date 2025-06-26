import os
import psycopg2
from playwright.sync_api import sync_playwright

DB_HOST = os.getenv("DB_HOST")
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")

def save_to_postgres(data):
    conn = psycopg2.connect(
        host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD
    )
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
        """, (job["title"], job["company"], job["location"], job["link"]))
    conn.commit()
    cur.close()
    conn.close()

def scrape_jobs():
    results = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto("https://example.com/jobs")
        jobs = page.query_selector_all(".job-listing")
        for job in jobs:
            title = job.query_selector("h2").inner_text()
            company = job.query_selector(".company").inner_text()
            location = job.query_selector(".location").inner_text()
            link = job.query_selector("a").get_attribute("href")
            results.append({"title": title, "company": company, "location": location, "link": link})
        browser.close()
    return results

if __name__ == "__main__":
    jobs = scrape_jobs()
    save_to_postgres(jobs)
