# Weekly Trakt Queue

This project fetches a list of trending movies from a Trakt-powered RSS feed and keeps a small rotating queue of torrents on Put.io.

## Features

- Only five items from the RSS feed are seeded at any time.
- Each week the `/weekly-downloads` folder is cleared and refilled with five new torrents.
- Magnet links are detected from standard `<link>` elements or enclosure links in the RSS feed.
- Optionally sends an email summary with movie posters and overviews from TMDB API.

## Requirements

- Python 3.10+
- See `requirements.txt` for required packages.

## Configuration

Create a `.env` file with the following variables:

```
RSS_URL=<Comma-separated list of RSS feed URLs>
PUTIO_TOKEN=<Put.io OAuth token>
WEEKLY_FOLDER_ID=<folder id of /weekly-downloads>
TMDB_API_KEY=<TMDB API key for movie details>
```

## Usage

Install dependencies:

```bash
pip install -r requirements.txt
```

Seed five magnets from the RSS feed:

```bash
python weekly_queue.py --seed
```

Refresh the folder weekly (e.g. from cron on Fridays):

```bash
python weekly_queue.py --refresh
```

# Weekly Trakt Queue

This project fetches a list of trending movies from an RSS feed and seeds a rotating queue of torrents in a Put.io folder.

## Features

- Selects up to five random items from the RSS feed each run.
- Clears the configured Put.io folder and refills it with the selected torrents.
- Detects magnet URLs from `<link>` elements or enclosure links in the RSS feed.
- Optionally emails a summary with posters and overviews from TMDB API after seeding.

## Requirements

- Python 3.10+
- See `requirements.txt` for required packages.

## Configuration

Create a `.env` file with the following variables:

```
RSS_URL=<Comma-separated list of RSS feed URLs>
PUTIO_TOKEN=<Put.io OAuth access token>
WEEKLY_FOLDER_ID=<Put.io folder ID to seed>
# optional email configuration
SMTP_SERVER=<SMTP server>
SMTP_PORT=<SMTP port, default 587>
SMTP_USERNAME=<SMTP username>
SMTP_PASSWORD=<SMTP password>
EMAIL_FROM=<from address>
EMAIL_TO=<destination address>
TMDB_API_KEY=<TMDB API key for movie details>
```

## Usage

Install dependencies:

```bash
pip install -r requirements.txt
```

Seed five random magnets from the RSS feed:

```bash
python weekly_queue.py --seed
```

Refresh the folder (clear and reseed):

```bash
python weekly_queue.py --refresh
```

(Optional) Add a cron job to run weekly, e.g. every Friday at 9 AM:

```cron
0 9 * * FRI cd /path/to/put-theatre && python weekly_queue.py --refresh
```
