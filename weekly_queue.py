import os
import logging
from typing import List, Dict

import feedparser
import putiopy
import requests
import random
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')


def load_config():
    load_dotenv()
    config = {
        'RSS_URL': os.getenv('RSS_URL'),
        'PUTIO_TOKEN': os.getenv('PUTIO_TOKEN'),
        'WEEKLY_FOLDER_ID': os.getenv('WEEKLY_FOLDER_ID'),
    }
    missing = [k for k, v in config.items() if not v]
    if missing:
        raise SystemExit(f"Missing required config: {', '.join(missing)}")
    return config


def fetch_rss_items(rss_url: str, limit: int = 5) -> List[Dict[str, str]]:
    """Return up to ``limit`` items from the RSS feed."""
    logging.info('Fetching RSS feed')
    feed = feedparser.parse(requests.get(rss_url, timeout=10).text)
    # Collect all magnet links
    items = []
    for entry in feed.entries:
        magnet_url = None
        for link in entry.get('links', []):
            if link.get('type') == 'application/x-bittorrent' and link.get('href', '').startswith('magnet:'):
                magnet_url = link['href']
                break
        if not magnet_url:
            direct_link = entry.get('link')
            if direct_link and direct_link.startswith('magnet:'):
                magnet_url = direct_link
        if magnet_url:
            items.append({'title': entry.get('title', 'unknown'), 'magnet_url': magnet_url})
    if not items:
        logging.info('No magnet links found in RSS')
        return []
    # Select random sample up to limit
    if len(items) <= limit:
        selected = items
    else:
        selected = random.sample(items, limit)
    logging.info('Selected %d random items from RSS', len(selected))
    return selected


def seed_magnets(client: putiopy.Client, magnets: List[Dict[str, str]], parent_id: int):
    for item in magnets:
        try:
            client.Transfer.add_url(item['magnet_url'], parent_id=parent_id)
            logging.info('Seeded %s', item['title'])
        except Exception as e:
            logging.error('Failed to seed %s: %s', item['title'], e)


def refresh_weekly(client: putiopy.Client, rss_url: str, weekly_id: int):
    """Clear the weekly folder and seed five new torrents."""
    logging.info('Clearing weekly folder')
    existing = client.File.list(parent_id=weekly_id)
    for f in existing:
        try:
            # Delete using object method if available, otherwise fall back to delete_multi
            if hasattr(f, 'delete'):
                f.delete()
                file_name = f.name
            else:
                file_id = f
                file_name = str(f)
                client.File.delete_multi([file_id])
            logging.info('Deleted %s', file_name)
        except Exception as e:
            logging.error('Failed to delete %s: %s', file_name, e)

    items = fetch_rss_items(rss_url, limit=5)
    seed_magnets(client, items, weekly_id)


def main():
    import argparse

    parser = argparse.ArgumentParser(description='Weekly Trakt Queue')
    parser.add_argument('--seed', action='store_true', help='Seed five torrents into the weekly folder')
    parser.add_argument('--refresh', action='store_true', help='Clear folder and seed five new torrents')
    args = parser.parse_args()

    if not args.seed and not args.refresh:
        parser.error('Specify --seed or --refresh')

    cfg = load_config()
    client = putiopy.Client(cfg['PUTIO_TOKEN'])

    if args.refresh:
        refresh_weekly(client, cfg['RSS_URL'], int(cfg['WEEKLY_FOLDER_ID']))
    elif args.seed:
        items = fetch_rss_items(cfg['RSS_URL'], limit=5)
        seed_magnets(client, items, int(cfg['WEEKLY_FOLDER_ID']))


if __name__ == '__main__':
    main()
