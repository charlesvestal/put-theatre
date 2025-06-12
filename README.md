# Weekly Trakt Queue

This project fetches a list of trending movies from a Trakt-powered RSS feed and keeps a small rotating queue of torrents on Put.io.

## Features

- Only five items from the RSS feed are seeded at any time.
- Each week the `/weekly-downloads` folder is cleared and refilled with five new torrents.

## Requirements

- Python 3.10+
- See `requirements.txt` for required packages.

## Configuration

Create a `.env` file with the following variables:

```
RSS_URL=<RSS feed with token>
PUTIO_TOKEN=<Put.io OAuth token>
WEEKLY_FOLDER_ID=<folder id of /weekly-downloads>
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
