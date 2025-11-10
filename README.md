# arXiv Crawler

This repository contains a simple arXiv metadata crawler that fetches recent listings for given subjects and stores metadata into a JSON file.

Usage

- Install dependencies:

  pip install -r requirements.txt

- Run locally (example):

  python crawler.py --subjects "cs.AI,cs.LG" --output data/papers.json

- Or provide a subjects file (one subject per line):

  python crawler.py --subjects-file app/subjects.txt --output data/papers.json

GitHub Actions

The workflow `.github/workflows/python-app.yml` will run the crawler daily and can also be triggered manually.

Notes

- The script deduplicates papers by arXiv short id (doi field in the data) and keeps all data in the specified JSON file.
- Keep the `app/subjects.txt` file under version control to define the subjects you want to crawl.
