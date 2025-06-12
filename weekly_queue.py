import os
import logging
from typing import List, Dict, Optional

import feedparser
import putiopy
import requests
import random
from dotenv import load_dotenv

import re

def clean_title(raw_title: str) -> str:
    """Clean raw torrent title into a movie name usable by OMDb."""
    # Replace dots and underscores with spaces
    title = raw_title.replace('.', ' ').replace('_', ' ')
    # Remove common quality and source tags
    title = re.sub(r'\b(480p|720p|1080p|2160p|4K|x264|x265|WEBRip|WEB)\b', '', title, flags=re.IGNORECASE)
    # Remove bracketed or parenthesized group tags
    title = re.sub(r'[\[\(].*?[\]\)]', '', title)
    # Collapse multiple spaces and strip
    return re.sub(r'\s+', ' ', title).strip()

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
        'TMDB_API_KEY': os.getenv('TMDB_API_KEY'),
    }
    required = ['RSS_URL', 'PUTIO_TOKEN', 'WEEKLY_FOLDER_ID']
    missing = [k for k in required if not config.get(k)]
    if missing:
        raise SystemExit(f"Missing required config: {', '.join(missing)}")
    return config


def fetch_rss_items(rss_url: str, limit: Optional[int] = 5) -> List[Dict[str, str]]:
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
            items.append({
                'title': entry.get('title', 'unknown'),
                'magnet_url': magnet_url,
                'imdb_id': entry.get('id') or entry.get('guid')
            })
    if limit is None:
        logging.info('Returning all %d items from RSS %s', len(items), rss_url)
        return items
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


def fetch_movie_info(title: str, tmdb_api_key: str, imdb_id: Optional[str] = None) -> Dict[str, str]:
    """Return movie info from TMDB API."""
    if not tmdb_api_key:
        logging.warning("No TMDB API key provided; using raw title.")
        return {'title': title, 'poster': '', 'plot': ''}
    base_url = 'https://api.themoviedb.org/3'
    headers = {'Accept': 'application/json'}
    movie_data = None
    try:
        if imdb_id:
            logging.info("Looking up TMDB by IMDb ID: %s", imdb_id)
            find_url = f"{base_url}/find/{imdb_id}"
            params = {'api_key': tmdb_api_key, 'external_source': 'imdb_id'}
            resp = requests.get(find_url, params=params, headers=headers, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            results = data.get('movie_results', [])
            movie_data = results[0] if results else None
        if not movie_data:
            cleaned = clean_title(title)
            logging.info("Searching TMDB for title: %s", cleaned)
            search_url = f"{base_url}/search/movie"
            params = {'api_key': tmdb_api_key, 'query': cleaned}
            resp = requests.get(search_url, params=params, headers=headers, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            results = data.get('results', [])
            movie_data = results[0] if results else None
        if not movie_data:
            logging.warning("TMDB did not find data for '%s'", title)
            return {'title': title, 'poster': '', 'plot': ''}
        movie_id = movie_data.get('id')
        details_url = f"{base_url}/movie/{movie_id}"
        params = {'api_key': tmdb_api_key}
        resp = requests.get(details_url, params=params, headers=headers, timeout=10)
        resp.raise_for_status()
        details = resp.json()
        poster_path = details.get('poster_path')
        poster_url = f"https://image.tmdb.org/t/p/w500{poster_path}" if poster_path else ''
        overview = details.get('overview', '')
        return {'title': details.get('title', title), 'poster': poster_url, 'plot': overview}
    except Exception as e:
        logging.error("Failed to fetch TMDB info for %s: %s", title, e)
        return {'title': title, 'poster': '', 'plot': ''}


def send_movies_email(items: List[Dict[str, str]], cfg: Dict[str, str]):
    """Send an email with movie details and poster URLs."""
    if not cfg.get('EMAIL_TO'):
        return
    movie_infos = [
        fetch_movie_info(
            i['title'],
            cfg.get('TMDB_API_KEY', ''),
            i.get('imdb_id')
        )
        for i in items
    ]

    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText
    import smtplib

    msg = MIMEMultipart()
    msg['Subject'] = 'Weekly Downloads'
    msg['From'] = cfg.get('EMAIL_FROM', cfg.get('SMTP_USERNAME', ''))
    msg['To'] = cfg['EMAIL_TO']

    # Build HTML email: posters in a row, then titles and plots
    html = ['<html><body>']
    # Posters row
    html.append('<div style="display:flex; gap:10px;">')
    for m in movie_infos:
        if m['poster']:
            html.append(f'<img src="{m["poster"]}" alt="poster" style="max-height:300px; margin-right:10px;"/>')
        else:
            html.append('<div style="width:200px; height:300px; background:#ccc; display:flex; align-items:center; justify-content:center;">No image</div>')
    html.append('</div>')
    # Movie titles and plots
    for m in movie_infos:
        html.append(f"<h2>{m['title']}</h2>")
        if m['plot']:
            html.append(f"<p>{m['plot']}</p>")
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

    # Aggregate items from multiple RSS feeds
    feed_urls = [u.strip() for u in rss_url.split(',')]
    all_items = []
    for url in feed_urls:
        all_items.extend(fetch_rss_items(url, limit=None))
    # Deduplicate by IMDb ID or magnet URL
    seen = set()
    unique_items = []
    for itm in all_items:
        key = itm.get('imdb_id') or itm.get('magnet_url')
        if key and key not in seen:
            seen.add(key)
            unique_items.append(itm)
    # Choose up to five random unique movies
    if len(unique_items) <= 5:
        selected = unique_items
    else:
        selected = random.sample(unique_items, 5)
    logging.info('Selected %d unique items across feeds', len(selected))
    # Seed and return
    seed_magnets(client, selected, weekly_id)
    return selected


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
