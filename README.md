# Weekly Trakt Queue

This project fetches a list of trending movies from a Trakt-powered RSS feed and manages a weekly rotation of downloads on Put.io.

## Features

- Seed all magnet links from the RSS feed into your `/downloads` folder.
- Every week move and copy a selection of items into `/weekly-downloads` for easy viewing.

## Requirements

- Python 3.10+
- See `requirements.txt` for required packages.

## Configuration

Create a `.env` file with the following variables:

```
RSS_URL=<RSS feed with token>
PUTIO_TOKEN=<Put.io OAuth token>
DOWNLOADS_FOLDER_ID=<folder id of /downloads>
ARCHIVE_FOLDER_ID=<folder id of /archive>
WEEKLY_FOLDER_ID=<folder id of /weekly-downloads>
```

## Usage

Install dependencies:

```bash
pip install -r requirements.txt
```

Seed magnets from the RSS feed:

```bash
python weekly_queue.py --seed
```

Run the weekly shuffle (e.g. from cron on Fridays):

```bash
python weekly_queue.py --shuffle
```
