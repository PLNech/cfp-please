#!/usr/bin/env python3
"""Daemon script to fetch city images over multiple hours.

Respects Unsplash rate limit (50 req/hour demo mode).
Handles 403 with exponential backoff, retries every 5 min.

Usage:
    nohup poetry run python -m cfp_pipeline.scripts.fetch_city_images_daemon &
    tail -f data/city_images_daemon.log
"""

import logging
import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

import httpx

# Config
BATCH_SIZE = 45  # Stay under 50/hour rate limit
BASE_RETRY_MINUTES = 5  # Start with 5 min backoff
MAX_RETRY_MINUTES = 65  # Max backoff ~1 hour
PROJECT_ROOT = Path(__file__).parent.parent.parent
LOG_FILE = PROJECT_ROOT / "data" / "city_images_daemon.log"


def load_env():
    """Load .env file into environment."""
    env_path = PROJECT_ROOT / '.env'
    if env_path.exists():
        with open(env_path) as f:
            for line in f:
                if '=' in line and not line.startswith('#'):
                    k, v = line.strip().split('=', 1)
                    os.environ[k] = v


def setup_logging():
    """Setup logging to file and console."""
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

    # Clear old handlers
    root = logging.getLogger()
    for h in root.handlers[:]:
        root.removeHandler(h)

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s | %(message)s',
        handlers=[
            logging.FileHandler(LOG_FILE),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger(__name__)


def fetch_single_city(city: str, client: httpx.Client) -> list[dict] | None:
    """Fetch images for one city. Returns None on rate limit, [] on not found."""
    query = f"{city} iconic skyline cityscape"
    try:
        resp = client.get("/search/photos", params={
            "query": query,
            "per_page": 5,
            "orientation": "landscape",
            "content_filter": "high",
        })

        if resp.status_code == 403:
            return None  # Rate limited

        resp.raise_for_status()
        data = resp.json()

        images = []
        for photo in data.get("results", []):
            images.append({
                "id": photo["id"],
                "url": photo["urls"]["regular"],
                "thumb": photo["urls"]["small"],
                "blur_hash": photo.get("blur_hash"),
                "photographer": photo["user"]["name"],
                "photographer_url": photo["user"]["links"]["html"],
            })
        return images

    except httpx.HTTPStatusError as e:
        if e.response.status_code == 403:
            return None  # Rate limited
        return []  # Other error
    except Exception:
        return []


def run_daemon():
    """Run the daemon with exponential backoff on rate limits."""
    load_env()
    log = setup_logging()

    sys.path.insert(0, str(PROJECT_ROOT))
    from cfp_pipeline.scripts.fetch_city_images import (
        load_city_images,
        save_city_images,
        get_unique_cities,
        enrich_algolia_records,
    )

    log.info("=" * 60)
    log.info("City Images Daemon Started (with exponential backoff)")
    log.info(f"Batch size: {BATCH_SIZE} | Base retry: {BASE_RETRY_MINUTES}min")
    log.info("=" * 60)

    backoff_minutes = BASE_RETRY_MINUTES
    consecutive_rate_limits = 0

    # Unsplash client
    access_key = os.environ.get("UNSPLASH_ACCESS_KEY")
    if not access_key:
        log.error("UNSPLASH_ACCESS_KEY not set!")
        return

    client = httpx.Client(
        base_url="https://api.unsplash.com",
        headers={"Authorization": f"Client-ID {access_key}"},
        timeout=30.0,
    )

    while True:
        city_images = load_city_images()
        all_cities = get_unique_cities(prioritize=True)
        missing = [c for c in all_cities if c not in city_images]

        if not missing:
            log.info("All cities have images! Final enrichment...")
            enrich_algolia_records()
            log.info("Done!")
            break

        log.info(f"\n--- Fetching ({len(city_images)}/{len(all_cities)} done, {len(missing)} remaining) ---")

        fetched = 0
        rate_limited = False

        for city in missing[:BATCH_SIZE]:
            images = fetch_single_city(city, client)

            if images is None:
                # Rate limited
                log.warning(f"Rate limited at {city}")
                rate_limited = True
                break

            if images:
                city_images[city] = images
                log.info(f"  {city}: {len(images)} images")
                fetched += 1
            else:
                log.info(f"  {city}: no images found")

            time.sleep(1.2)  # ~50/min safe

            # Save every 10
            if fetched > 0 and fetched % 10 == 0:
                save_city_images(city_images)

        # Save progress
        if fetched > 0:
            save_city_images(city_images)
            log.info(f"Saved {fetched} new cities")

            # Enrich Algolia
            try:
                enrich_algolia_records()
                log.info("Algolia enriched")
            except Exception as e:
                log.error(f"Enrich error: {e}")

        # Handle rate limit with exponential backoff
        if rate_limited:
            consecutive_rate_limits += 1
            backoff_minutes = min(BASE_RETRY_MINUTES * (2 ** (consecutive_rate_limits - 1)), MAX_RETRY_MINUTES)
            next_try = datetime.now() + timedelta(minutes=backoff_minutes)
            log.info(f"Rate limited. Backoff {backoff_minutes}min until {next_try.strftime('%H:%M:%S')}")

            # Sleep with status updates every 5 min
            sleep_secs = backoff_minutes * 60
            while sleep_secs > 0:
                time.sleep(min(300, sleep_secs))
                sleep_secs -= 300
                if sleep_secs > 0:
                    log.info(f"  ...{sleep_secs // 60}min until retry")
        else:
            # Success - reset backoff
            consecutive_rate_limits = 0
            backoff_minutes = BASE_RETRY_MINUTES

            # If we got a full batch, continue immediately
            if fetched >= BATCH_SIZE:
                log.info("Full batch done, continuing...")
                continue

            # Otherwise wait standard interval
            log.info(f"Partial batch. Waiting {BASE_RETRY_MINUTES}min...")
            time.sleep(BASE_RETRY_MINUTES * 60)

    client.close()
    log.info("=" * 60)
    log.info("Daemon Complete!")
    log.info("=" * 60)


if __name__ == "__main__":
    run_daemon()
