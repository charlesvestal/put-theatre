import os
import logging
from typing import List, Dict, Optional

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
        'SMTP_SERVER': os.getenv('SMTP_SERVER'),
        'SMTP_PORT': os.getenv('SMTP_PORT', '587'),
        'SMTP_USERNAME': os.getenv('SMTP_USERNAME'),
        'SMTP_PASSWORD': os.getenv('SMTP_PASSWORD'),
        'EMAIL_FROM': os.getenv('EMAIL_FROM'),
        'EMAIL_TO': os.getenv('EMAIL_TO'),
        'OMDB_API_KEY': os.getenv('OMDB_API_KEY'),
    }
    required = ['RSS_URL', 'PUTIO_TOKEN', 'WEEKLY_FOLDER_ID']
    missing = [k for k in required if not config.get(k)]
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


def fetch_movie_info(title: str, api_key: str) -> Dict[str, str]:
    """Return movie info from OMDb API."""
    if not api_key:
        return {'title': title, 'poster': '', 'plot': ''}
    try:
        resp = requests.get(
            'https://www.omdbapi.com/',
            params={'t': title, 'apikey': api_key},
            timeout=10,
        )
        data = resp.json()
        if data.get('Response') == 'True':
            return {
                'title': data.get('Title', title),
                'poster': data.get('Poster', ''),
                'plot': data.get('Plot', ''),
            }
    except Exception as e:
        logging.error('Failed to fetch info for %s: %s', title, e)
    return {'title': title, 'poster': '', 'plot': ''}


def send_movies_email(items: List[Dict[str, str]], cfg: Dict[str, str]):
    """Send an email with movie details and poster URLs."""
    if not cfg.get('EMAIL_TO'):
        return
    movie_infos = [fetch_movie_info(i['title'], cfg.get('OMDB_API_KEY', '')) for i in items]

    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText
    import smtplib

    msg = MIMEMultipart()
    msg['Subject'] = 'Weekly Downloads'
    msg['From'] = cfg.get('EMAIL_FROM', cfg.get('SMTP_USERNAME', ''))
    msg['To'] = cfg['EMAIL_TO']

    html = ['<html><body>']
    for m in movie_infos:
        html.append(f"<h2>{m['title']}</h2>")
        if m['poster']:
            html.append('<img src="{}" alt="poster"><br>'.format(m['poster']))
        if m['plot']:
            html.append('<p>{}</p>'.format(m['plot']))
    html.append('</body></html>')
    msg.attach(MIMEText(''.join(html), 'html'))

    try:
        with smtplib.SMTP(cfg['SMTP_SERVER'], int(cfg.get('SMTP_PORT', 587))) as s:
            s.starttls()
            if cfg.get('SMTP_USERNAME') and cfg.get('SMTP_PASSWORD'):
                s.login(cfg['SMTP_USERNAME'], cfg['SMTP_PASSWORD'])
            s.sendmail(msg['From'], [cfg['EMAIL_TO']], msg.as_string())
        logging.info('Sent email to %s', cfg['EMAIL_TO'])
    except Exception as e:
        logging.error('Failed to send email: %s', e)


def seed_magnets(client: putiopy.Client, magnets: List[Dict[str, str]], parent_id: int):
    for item in magnets:
        try:
            client.Transfer.add_url(item['magnet_url'], parent_id=parent_id)
            logging.info('Seeded %s', item['title'])
        except Exception as e:
            logging.error('Failed to seed %s: %s', item['title'], e)


def refresh_weekly(client: putiopy.Client, rss_url: str, weekly_id: int) -> List[Dict[str, str]]:
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
    return items


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
        items = refresh_weekly(client, cfg['RSS_URL'], int(cfg['WEEKLY_FOLDER_ID']))
        send_movies_email(items, cfg)
    elif args.seed:
        items = fetch_rss_items(cfg['RSS_URL'], limit=5)
        seed_magnets(client, items, int(cfg['WEEKLY_FOLDER_ID']))
        send_movies_email(items, cfg)


if __name__ == '__main__':
    main()
