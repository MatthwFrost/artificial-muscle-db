"""CLI to extract materials from a paper and write them to the database.

Usage:
    python -m muscle_worker.extract_paper URL [--class CLASS_SLUG] [--title TITLE]

Example:
    python -m muscle_worker.extract_paper \
        https://en.wikipedia.org/wiki/Liquid_crystal_elastomer \
        --class lce --title "Wikipedia: LCE"
"""

from __future__ import annotations

import argparse

import structlog

from .pipeline import extract_paper


def main() -> None:
    structlog.configure(
        processors=[
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.dev.ConsoleRenderer(),
        ]
    )

    parser = argparse.ArgumentParser(description="Extract materials from a paper URL into the database.")
    parser.add_argument("url", help="URL of the paper or page to extract from")
    parser.add_argument("--class", dest="class_slug", default="lce", help="Taxonomy class slug (default: lce)")
    parser.add_argument("--subclass", dest="subclass_slug", default=None, help="Taxonomy subclass slug")
    parser.add_argument("--title", default="Untitled", help="Paper title (used if paper is new)")
    args = parser.parse_args()

    print(f"Extracting from: {args.url}")
    print(f"Class: {args.class_slug}")
    print()

    result = extract_paper(
        url=args.url,
        class_slug=args.class_slug,
        subclass_slug=args.subclass_slug,
        title=args.title,
    )

    print()
    print("=" * 60)
    print(f"Status:             {result.status}")
    print(f"Paper ID:           {result.paper_id}")
    print(f"Materials inserted: {result.materials_inserted}")
    print(f"Material IDs:       {result.material_ids}")
    print(f"Credits used:       {result.credits_used}")
    print(f"Duration:           {result.duration_s:.1f}s")
    if result.error:
        print(f"Error:              {result.error}")
    print("=" * 60)


if __name__ == "__main__":
    main()
