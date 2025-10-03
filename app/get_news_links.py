from dotenv import load_dotenv
from typing import List, Dict
import os
import requests

load_dotenv()

TANK01_API_KEY = os.getenv("TANK01_API_KEY")
TANK_01_NFL_BASE_URL = "https://tank01-nfl-live-in-game-real-time-statistics-nfl.p.rapidapi.com"

#Get All Recent ESPN News Links From TANK01
def get_nfl_links():
    url = f"{TANK_01_NFL_BASE_URL}/getNFLNews?topNews=true&recentNews=true&maxItems=20"
    headers = {
        "x-rapidapi-host": "tank01-nfl-live-in-game-real-time-statistics-nfl.p.rapidapi.com",
        "x-rapidapi-key": TANK01_API_KEY
    }

    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()

        data = response.json()

        results: List[Dict[str, str]] = []
        for item in data.get("body", []):
            link = item.get("link")
            title = item.get("title")
            if "espn" in link:
                results.append({"url": link, "title": title})
        return results
    except requests.exceptions.RequestException as e:
        print("Error Fetching NFL Links:", e)
        return []

#CLI Test
if __name__ == "__main__":
    items = get_nfl_links()
    for i, it in enumerate(items, 1):
        print(f"{i}. {it['title']}\n   {it['url']}\n")