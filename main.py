from fastapi import FastAPI, Query, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from linkedin_jobs_scraper import LinkedinScraper
from linkedin_jobs_scraper.events import Events, EventData
from linkedin_jobs_scraper.query import Query, QueryOptions, QueryFilters
from linkedin_jobs_scraper.filters import RelevanceFilters, TimeFilters, TypeFilters
import requests
from bs4 import BeautifulSoup


app = FastAPI()

class JobFilter(BaseModel):
    keyword: str
    locations: Optional[List[str]] = None
    limit: int = 25
    relevance: Optional[str] = "RECENT"
    type: Optional[List[str]] = ["FULL_TIME"]
    cookie: str


def get_company_link(job_url):
    response = requests.get(job_url, headers={'User-Agent': 'Mozilla/5.0'})
    soup = BeautifulSoup(response.text, 'html.parser')
    for tag in soup.find_all('a', href=True):
        href = tag['href']
        if '/company/' in href:
            return href.split('?')[0]
    return ''

@app.post("/search")
async def search_jobs(filters: JobFilter):
    jobs = []
    if not filters.cookie:
        raise HTTPException(status_code=400, detail="Cookie is required")
    def on_data(data: EventData):
        job_data = {
            "title": data.title,
            "company": data.company,
            "company_link": get_company_link(data.link),
            "date": str(data.date),
            "date_text": data.date_text,
            "link": data.link,
            "description_length": len(data.description)
        }
        jobs.append(job_data)

    scraper = LinkedinScraper(headless=True, max_workers=1, slow_mo=0.5, page_load_timeout=40)
    scraper.on(Events.DATA, on_data)
    scraper.on(Events.ERROR, lambda e: print('[ERROR]', e))
    scraper.on(Events.END, lambda: print('[END]'))

    scraper.session_cookie_value = filters.cookie

    q = Query(
        query=filters.keyword,
        options=QueryOptions(
            locations=filters.locations or 'United States',
            apply_link=True,
            skip_promoted_jobs=True,
            limit=filters.limit or 25,
            filters=QueryFilters(
                relevance=RelevanceFilters[filters.relevance or "RECENT"],
                type=[TypeFilters[t] for t in filters.type or ["FULL_TIME"]]
            )
        )
    )
    q.validate()
    scraper.run(q)
    return {"jobs": jobs}
