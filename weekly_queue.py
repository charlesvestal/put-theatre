import os
import random
import logging
from datetime import datetime
from typing import List, Dict

import feedparser
import putiopy
import requests
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')


def load_config():
    load_dotenv()
    config = {
        'RSS_URL': os.getenv('RSS_URL'),
        'PUTIO_TOKEN': os.getenv('PUTIO_TOKEN'),
        'DOWNLOADS_FOLDER_ID': os.getenv('DOWNLOADS_FOLDER_ID'),
        'ARCHIVE_FOLDER_ID': os.getenv('ARCHIVE_FOLDER_ID'),
        'WEEKLY_FOLDER_ID': os.getenv('WEEKLY_FOLDER_ID'),
    }
    missing = [k for k, v in config.items() if not v]
    if missing:
        raise SystemExit(f"Missing required config: {', '.join(missing)}")
    return config


def fetch_rss_items(rss_url: str) -> List[Dict[str, str]]:
    logging.info('Fetching RSS feed')
    feed = feedparser.parse(requests.get(rss_url, timeout=10).text)
    items = []
    for entry in feed.entries:
        magnet_url = None
        for link in entry.get('links', []):
            if link.get('type') == 'application/x-bittorrent' and link.get('href', '').startswith('magnet:'):
                magnet_url = link['href']
                break
        if magnet_url:
            items.append({'title': entry.get('title', 'unknown'), 'magnet_url': magnet_url})
    logging.info('Found %d items in RSS', len(items))
    return items


def seed_magnets(client: putiopy.Client, magnets: List[Dict[str, str]], parent_id: int):
    for item in magnets:
        try:
            client.Transfer.add_url(item['magnet_url'], parent_id=parent_id)
            logging.info('Seeded %s', item['title'])
        except Exception as e:
            logging.error('Failed to seed %s: %s', item['title'], e)


def weekly_shuffle(client: putiopy.Client, downloads_id: int, archive_id: int, weekly_id: int):
    logging.info('Running weekly shuffle')
    downloads = client.File.list(parent_id=downloads_id)
    if len(downloads) >= 10:
        sample_10 = random.sample(downloads, 10)
        for f in sample_10:
            client.File.move(f.id, weekly_id)
            logging.info('Moved %s to weekly', f.name)
    else:
        logging.warning('Not enough files in downloads for moving')

    downloads = client.File.list(parent_id=downloads_id)
    recent_5 = sorted(downloads, key=lambda f: f.created_at, reverse=True)[:5]
    for f in recent_5:
        client.File.copy(f.id, weekly_id)
        logging.info('Copied recent %s to weekly', f.name)

    archive = client.File.list(parent_id=archive_id)
    if len(archive) >= 5:
        sample_5 = random.sample(archive, 5)
        for f in sample_5:
            client.File.copy(f.id, weekly_id)
            logging.info('Copied archive %s to weekly', f.name)
    else:
        logging.warning('Not enough files in archive for sampling')


def main():
    import argparse

    parser = argparse.ArgumentParser(description='Weekly Trakt Queue')
    parser.add_argument('--seed', action='store_true', help='Fetch RSS and seed magnets')
    parser.add_argument('--shuffle', action='store_true', help='Perform weekly shuffle')
    args = parser.parse_args()

    if not args.seed and not args.shuffle:
        parser.error('Specify --seed and/or --shuffle')

    cfg = load_config()
    client = putiopy.Client(cfg['PUTIO_TOKEN'])

    if args.seed:
        items = fetch_rss_items(cfg['RSS_URL'])
        seed_magnets(client, items, int(cfg['DOWNLOADS_FOLDER_ID']))

    if args.shuffle:
        weekly_shuffle(
            client,
            int(cfg['DOWNLOADS_FOLDER_ID']),
            int(cfg['ARCHIVE_FOLDER_ID']),
            int(cfg['WEEKLY_FOLDER_ID']),
        )


if __name__ == '__main__':
    main()
