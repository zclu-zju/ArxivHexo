import datetime
import time
import json
import argparse
import logging
from pathlib import Path
from requests import Session
from lxml.etree import HTML
import arxiv

xpath_config = {
    "block1": '//*[@id="articles"]/dt',
    "abstract": './a[@title="Abstract"]',
}

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def _sanitize_doi(doi: str) -> str:
    return doi.replace("/", "_").replace(":", "_")


def load_index(index_path: Path):
    if not index_path.exists():
        return {"papers": {}}
    try:
        return json.loads(index_path.read_text(encoding="utf-8"))
    except Exception:
        logging.warning("Failed to read index; starting fresh: %s", index_path)
        return {"papers": {}}


def save_index(index_path: Path, index: dict):
    index_path.parent.mkdir(parents=True, exist_ok=True)
    index_path.write_text(
        json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    logging.info(
        "Index saved: %s (papers=%d)", index_path, len(index.get("papers", {}))
    )


def paper_summary(paper: dict) -> dict:
    return {
        "doi": paper["doi"],
        "title": paper["title"],
        "authors": paper["authors"],
        "published": paper.get("published"),
        "url": paper["url"],
    }


def save_paper_file(base_dir: Path, paper: dict):
    papers_dir = base_dir / "papers"
    papers_dir.mkdir(parents=True, exist_ok=True)
    filename = _sanitize_doi(paper["doi"]) + ".json"
    path = papers_dir / filename
    path.write_text(json.dumps(paper, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(path.relative_to(base_dir))


def build_subject_pages(
    base_dir: Path, subject: str, index: dict, page_size: int = 100
):
    # collect summaries for this subject
    summaries = []
    for doi, p in index.get("papers", {}).items():
        if subject in p.get("subjects", []):
            summaries.append(paper_summary(p))

    if not summaries:
        return 0

    # sort by published (newest first)
    try:
        summaries.sort(key=lambda x: x.get("published") or "", reverse=True)
    except Exception:
        pass

    subject_dir = base_dir / "subjects" / subject
    subject_dir.mkdir(parents=True, exist_ok=True)
    # write paginated pages
    for i in range(0, len(summaries), page_size):
        page = summaries[i : i + page_size]
        page_num = i // page_size + 1
        page_path = subject_dir / f"page_{page_num}.json"
        page_path.write_text(
            json.dumps(page, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    logging.info(
        "Built %d pages for subject %s",
        (len(summaries) + page_size - 1) // page_size,
        subject,
    )
    return (len(summaries) + page_size - 1) // page_size


def load_existing_papers(path: Path):
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return {p["doi"]: p for p in data}
    except Exception:
        logging.warning("Failed to read existing JSON; starting fresh: %s", path)
        return {}


def save_papers_to_json(path: Path, papers_by_doi: dict):
    papers = list(papers_by_doi.values())
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(papers, ensure_ascii=False, indent=2), encoding="utf-8")
    logging.info("Wrote %d papers to %s", len(papers), path)


def get_id_list(url: str):
    session = Session()
    session.headers.update({"User-Agent": "Mozilla/5.0 (compatible; arXivCrawler/1.0)"})
    resp = session.get(url, timeout=10)
    resp.raise_for_status()
    html = HTML(resp.text)
    block1 = html.xpath(xpath_config["block1"])
    id_list = []
    for b1 in block1:
        abstract = b1.xpath(xpath_config["abstract"])
        if abstract:
            doi = abstract[0].get("id")
            if doi:
                id_list.append(doi)
    return id_list


def fetch_arxiv_data(id_list):
    results = []
    client = arxiv.Client()
    for id_list_grouped in [id_list[i : i + 100] for i in range(0, len(id_list), 100)]:
        search = arxiv.Search(id_list=id_list_grouped)
        for result in client.results(search):
            paper = {
                "doi": result.get_short_id(),
                "url": result.entry_id,
                "title": result.title.strip(),
                "published": datetime.datetime.strftime(result.published, "%Y-%m-%d"),
                "authors": [a.name for a in result.authors],
                "subjects": [t for t in result.categories],
                "summary": result.summary.strip().replace("\n", " "),
            }
            results.append(paper)
    return results


def run(subjects, output_path: Path, delay=5):
    output_path = output_path.expanduser()
    base_dir = output_path.parent
    base_dir.mkdir(parents=True, exist_ok=True)
    index_path = base_dir / "index.json"
    index = load_index(index_path)
    total_new = 0
    for subject in subjects:
        url = f"https://arxiv.org/list/{subject}/recent?skip=0&show=2000"
        logging.info("Fetching list page for %s", subject)
        try:
            id_list = get_id_list(url)
        except Exception as e:
            logging.warning("Failed to fetch id list for %s: %s", subject, e)
            continue

        if not id_list:
            logging.info("No papers found for %s", subject)
            continue

        papers = fetch_arxiv_data(id_list)
        new_count = 0
        for p in papers:
            doi = p["doi"]
            if doi not in index.get("papers", {}):
                # save per-paper file and add to index
                relpath = save_paper_file(base_dir, p)
                p["_file"] = relpath
                index.setdefault("papers", {})[doi] = p
                new_count += 1
            else:
                # update existing metadata if changed
                existing = index["papers"][doi]
                # lightweight update: overwrite title/summary/authors/subjects/published/url
                for k in (
                    "title",
                    "summary",
                    "authors",
                    "subjects",
                    "published",
                    "url",
                ):
                    existing[k] = p.get(k, existing.get(k))

        total_new += new_count
        logging.info("Subject %s: %d new papers", subject, new_count)
        # rebuild subject pages so frontend can fetch paginated summaries
        build_subject_pages(base_dir, subject, index, page_size=100)
        # persist index after each subject
        save_index(index_path, index)
        time.sleep(delay)

    logging.info("Finished. Total new papers: %d", total_new)
    return total_new


def parse_args():
    p = argparse.ArgumentParser(description="arXiv crawler that saves metadata to JSON")
    p.add_argument(
        "--subjects-file",
        type=str,
        default="subjects.txt",
        help="path to subjects list",
    )
    p.add_argument(
        "--subjects",
        type=str,
        help="comma-separated list of subjects, overrides subjects-file",
    )
    p.add_argument(
        "--output", type=str, default="data/papers.json", help="output JSON path"
    )
    p.add_argument(
        "--delay", type=int, default=5, help="delay between subjects (seconds)"
    )
    return p.parse_args()


if __name__ == "__main__":
    args = parse_args()
    if args.subjects:
        subjects = [s.strip() for s in args.subjects.split(",") if s.strip()]
    else:
        subjects_path = Path(args.subjects_file)
        if not subjects_path.exists():
            logging.error("Subjects file not found: %s", subjects_path)
            raise SystemExit(2)
        subjects = [
            line.strip()
            for line in subjects_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

    out_path = Path(args.output)
    run(subjects, out_path, delay=args.delay)
