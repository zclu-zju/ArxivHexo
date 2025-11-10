"""Export crawler index to Hexo-friendly content.

Produces:
- <hexo_dir>/source/data/subjects/<subject>/page_<n>.json  (paginated summaries)
- <hexo_dir>/source/_posts/highlights/<slug>.md             (small set of highlighted posts)

This is intentionally simple: CI can upload the produced content as an artifact
or you can include it into an existing Hexo site under the given directory.
"""

from pathlib import Path
import argparse
import json
import logging
import datetime

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def _sanitize(name: str) -> str:
    return "".join(c if c.isalnum() or c in "-_" else "_" for c in name)


def paper_summary(paper: dict) -> dict:
    return {
        "doi": paper["doi"],
        "title": paper["title"],
        "authors": paper.get("authors", []),
        "published": paper.get("published"),
        "url": paper.get("url"),
    }


def write_subject_pages(
    hexo_dir: Path, subject: str, papers: list, page_size: int = 100
):
    subject_dir = hexo_dir / "source" / "data" / "subjects" / subject
    subject_dir.mkdir(parents=True, exist_ok=True)
    for i in range(0, len(papers), page_size):
        page = papers[i : i + page_size]
        page_num = i // page_size + 1
        page_path = subject_dir / f"page_{page_num}.json"
        page_path.write_text(
            json.dumps(page, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    logging.info(
        "Wrote %d pages for subject %s",
        (len(papers) + page_size - 1) // page_size,
        subject,
    )


def write_highlights(hexo_dir: Path, subject: str, papers: list, count: int = 5):
    # kept for backwards compatibility; write a small number of highlight posts
    out_dir = hexo_dir / "source" / "_posts" / "highlights"
    out_dir.mkdir(parents=True, exist_ok=True)
    for p in papers:
        date = p.get("published") or datetime.date.today().isoformat()
        slug = _sanitize(p["doi"])
        filename = f"{date}-{slug}.md"
        # use json.dumps to produce safe, quoted representations
        title_line = "title: " + json.dumps(p.get("title", ""), ensure_ascii=False)
        date_line = "date: " + str(date)
        tags_line = "tags: " + json.dumps(p.get("subjects", []), ensure_ascii=False)
        authors_line = "authors: " + json.dumps(
            p.get("authors", []), ensure_ascii=False
        )
        doi_line = "doi: " + json.dumps(p.get("doi", ""), ensure_ascii=False)
        url_line = "original_url: " + json.dumps(p.get("url", ""), ensure_ascii=False)

        front = [
            "---",
            title_line,
            date_line,
            tags_line,
            authors_line,
            doi_line,
            url_line,
            "---",
            "",
        ]
        body = '<a href="{}">{}</a>\n'.format(
            p.get("url", ""), p.get("url", "")
        ) + p.get("summary", "")
        content = "\n".join(front) + body + "\n"
        (out_dir / filename).write_text(content, encoding="utf-8")
    logging.info(
        "Wrote %d highlight posts for subject %s", min(count, len(papers)), subject
    )


def write_papers_markdown(hexo_dir: Path, papers: list):
    """Write per-paper Markdown files into Hexo `source/_posts/papers/`.

    This produces one Markdown file per paper with front-matter and summary body so
    Hexo can generate static pages directly.
    """
    out_dir = hexo_dir / "source" / "_posts" / "papers"
    out_dir.mkdir(parents=True, exist_ok=True)
    for p in papers:
        date = p.get("published") or datetime.date.today().isoformat()
        slug = _sanitize(p["doi"])
        filename = f"{date}-{slug}.md"
        title_line = "title: " + json.dumps(p.get("title", ""), ensure_ascii=False)
        date_line = "date: " + str(date)
        tags_line = "tags: " + json.dumps(p.get("subjects", []), ensure_ascii=False)
        authors_line = "authors: " + json.dumps(
            p.get("authors", []), ensure_ascii=False
        )
        doi_line = "doi: " + json.dumps(p.get("doi", ""), ensure_ascii=False)
        url_line = "original_url: " + json.dumps(p.get("url", ""), ensure_ascii=False)

        front = [
            "---",
            title_line,
            date_line,
            tags_line,
            authors_line,
            doi_line,
            url_line,
            "---",
            "",
        ]
        # full summary (trim to reasonable length if needed)
        body = '<a href="{}">{}</a>\n'.format(
            p.get("url", ""), p.get("url", "")
        ) + p.get("summary", "")
        content = "\n".join(front) + body + "\n"
        (out_dir / filename).write_text(content, encoding="utf-8")
    logging.info("Wrote %d paper markdown files to %s", len(papers), out_dir)


def write_papers_by_subject_markdown(hexo_dir: Path, by_subject: dict):
    """Write per-paper Markdown files grouped by subject folders under
    `source/_posts/<subject>/` so Hexo can build static pages organized by category.
    """
    base = hexo_dir / "source" / "_posts"
    for subject, papers in by_subject.items():
        subject_dir = base / subject
        subject_dir.mkdir(parents=True, exist_ok=True)
        for p in papers:
            date = p.get("published") or datetime.date.today().isoformat()
            slug = _sanitize(p["doi"])
            filename = f"{date}-{slug}.md"
            title_line = "title: " + json.dumps(p.get("title", ""), ensure_ascii=False)
            date_line = "date: " + str(date)
            # include subjects as tags and subject as category
            tags_line = "tags: " + json.dumps(p.get("subjects", []), ensure_ascii=False)
            category_line = "categories: " + json.dumps([subject], ensure_ascii=False)
            authors_line = "authors: " + json.dumps(
                p.get("authors", []), ensure_ascii=False
            )
            doi_line = "doi: " + json.dumps(p.get("doi", ""), ensure_ascii=False)
            url_line = "original_url: " + json.dumps(
                p.get("url", ""), ensure_ascii=False
            )

            front = [
                "---",
                title_line,
                date_line,
                tags_line,
                category_line,
                authors_line,
                doi_line,
                url_line,
                "---",
                "",
            ]
            body = '<a href="{}">{}</a>\n'.format(
                p.get("url", ""), p.get("url", "")
            ) + p.get("summary", "")
            content = "\n".join(front) + body + "\n"
            (subject_dir / filename).write_text(content, encoding="utf-8")
    logging.info("Wrote markdown for %d subjects to %s", len(by_subject), base)


def main(
    index_path: Path,
    hexo_dir: Path,
    page_size: int = 100,
    highlights: int = 5,
    subject_prefixes: str = None,
):
    if not index_path.exists():
        logging.error("Index file not found: %s", index_path)
        raise SystemExit(2)
    index = json.loads(index_path.read_text(encoding="utf-8"))
    papers = list(index.get("papers", {}).values())
    # build subject -> papers map, filter by subject_prefixes if provided
    prefixes = []
    if subject_prefixes:
        prefixes = [x.strip().lower() for x in subject_prefixes.split(",") if x.strip()]

    by_subject = {}
    for p in papers:
        subjects = p.get("subjects", []) or []
        # filter subjects according to prefixes (if any)
        if prefixes:
            matching = [
                s
                for s in subjects
                if any(s.lower().startswith(pref) for pref in prefixes)
            ]
            if not matching:
                continue
        else:
            matching = subjects

        for s in matching:
            by_subject.setdefault(s, []).append(p)

    # sort each subject by published date desc
    for subject, group in by_subject.items():
        try:
            group.sort(key=lambda x: x.get("published") or "", reverse=True)
        except Exception:
            pass
        summaries = [paper_summary(p) for p in group]
        write_subject_pages(hexo_dir, subject, summaries, page_size=page_size)
        write_highlights(hexo_dir, subject, group, count=highlights)

    # export all papers as per-subject markdown so Hexo can build static pages
    write_papers_by_subject_markdown(hexo_dir, by_subject)

    logging.info("Export complete. Hexo content available at: %s", hexo_dir)


if __name__ == "__main__":
    p = argparse.ArgumentParser(
        description="Export crawler index into Hexo-friendly content"
    )
    p.add_argument(
        "--index",
        type=str,
        default="data/index.json",
        help="path to crawler index.json",
    )
    p.add_argument(
        "--hexo-dir",
        type=str,
        default="hexo_site",
        help="output directory for Hexo content",
    )
    p.add_argument("--page-size", type=int, default=100)
    p.add_argument("--highlights", type=int, default=5)
    p.add_argument(
        "--subject-prefixes",
        type=str,
        default="cs.,eess.",
        help="Comma-separated subject prefixes to include (e.g. 'cs.,eess.').",
    )
    args = p.parse_args()
    main(
        Path(args.index),
        Path(args.hexo_dir),
        page_size=args.page_size,
        highlights=args.highlights,
        subject_prefixes=args.subject_prefixes,
    )
