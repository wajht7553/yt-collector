#!/usr/bin/env python3
"""
YouTube Video Collection Toolkit

Usage:
    python collect.py init                              # Scaffold folders
    python collect.py download --class X                # Download or collect links for one class
    python collect.py download --all                    # Download or collect links for all classes
    python collect.py download --class X --keyword "q"  # Search specific keyword
    python collect.py download --class X --url "..."    # Download or save specific URL
    python collect.py download --all --links-only       # Save only video links & metadata (no video files)
    python collect.py status                            # Show progress
    python collect.py review                            # Launch review UI
    python collect.py dedup                             # Deduplicate references
    python collect.py clean                             # Organize accepted/rejected videos or link lists
    python collect.py export --dest <path>              # Export accepted videos/links to a dataset folder
"""

import sys
import argparse

from collector import config as cfg
from collector.reviewer import server
from collector import downloader, exporter, logger, scaffold


def cmd_init(args, config):
    """Initialize project folder structure."""
    print(f"\n  Initializing: {config['name']}")
    scaffold.print_tree(config)
    created = scaffold.scaffold(config)
    print(f"\n  Created {len(created)} directories and files.")
    print("  Edit project.yaml to define download behavior and specify keywords file.")
    print("  Then run: python collect.py download --class <ClassName>")


def cmd_download(args, config):
    """Download videos or collect video links."""
    if getattr(args, "links_only", False):
        config["links_only"] = True

    scaffold.scaffold(config)

    browser = args.browser or config.get("browser", "chrome")
    cookies_file = config.get("cookies_file", "")
    downloader.init(
        browser=browser, no_cookies=args.no_cookies, cookies_file=cookies_file
    )

    if args.all:
        for cls_name in cfg.get_class_names(config):
            print(f"\n{'='*60}")
            print(f"  CLASS: {cls_name}")
            print(f"{'='*60}")
            downloader.bulk_download(config, cls_name, args.max_per_keyword)
    elif args.cls:
        if args.keyword:
            downloader.download_keyword(
                config, args.keyword, args.cls, args.max_per_keyword
            )
        elif args.url:
            downloader.download_url(config, args.url, args.cls)
        else:
            downloader.bulk_download(config, args.cls, args.max_per_keyword)
    else:
        print("[ERROR] Specify --class <name> or --all")
        sys.exit(1)


def cmd_status(args, config):
    """Show collection progress."""
    logger.print_progress(config)

    csv_path = logger.get_csv_path(config)
    try:
        import csv

        with open(csv_path, "r", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        urls = [r.get("Source_URL", "") for r in rows if r.get("Source_URL")]
        unique = len(set(urls))
        print(f"  References: {len(rows)} rows ({unique} unique URLs)")
        if len(rows) > unique:
            print(
                f"  Run 'python collect.py dedup' to remove {len(rows) - unique} duplicates"
            )
    except FileNotFoundError:
        print("  No references yet. Run download first.")


def cmd_review(args, config):
    """Launch review UI."""
    server.serve(config, port=args.port)


def cmd_dedup(args, config):
    """Deduplicate references."""
    stats = logger.deduplicate(config)
    print(f"\n  Deduplication complete:")
    print(f"    Before: {stats['before']} rows")
    print(f"    After:  {stats['after']} rows")
    print(f"    Removed: {stats['removed']} duplicates")


def cmd_clean(args, config):
    """Organize accepted/rejected videos or link lists into their status files/folders."""
    moved = server.apply_decisions(config)
    if config.get("links_only"):
        print(f"\n  Synced link lists across class folders:")
        print(f"    Accepted links : {moved.get('accepted', 0)} (accepted_links.txt)")
        print(f"    Rejected links : {moved.get('rejected', 0)} (rejected_links.txt)")
        print(f"    Pending links  : {moved.get('pending', 0)} (pending_links.txt)")
    else:
        print(f"\n  Processed {moved.get('accepted', 0)} accepted and {moved.get('rejected', 0)} rejected items.")


def cmd_export(args, config):
    """Export accepted videos or links (and matching metadata) to an external dataset folder."""
    print(f"\n  Exporting accepted dataset items to: {args.dest}")
    stats = exporter.export_dataset(config, args.dest)

    for cls_name, count in sorted(stats["per_class"].items()):
        print(f"    {cls_name}: {count} exported")

    skip_note = (
        f", {stats['skipped_existing']} already present (skipped)"
        if stats["skipped_existing"]
        else ""
    )
    print(f"\n  Done. {stats['copied']} items exported{skip_note}.")
    print(
        f"  Metadata: {stats['metadata_rows']} rows written to source_references.csv"
    )


def main():
    parser = argparse.ArgumentParser(
        description="YouTube Video Collection Toolkit",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--config", default="project.yaml", help="Path to project config"
    )
    sub = parser.add_subparsers(dest="command", help="Available commands")

    # init
    sub.add_parser("init", help="Create folder structure from config")

    # download
    dl = sub.add_parser("download", help="Download videos or collect video links")
    dl.add_argument("--class", dest="cls", help="Target class name")
    dl.add_argument("--all", action="store_true", help="Download all classes")
    dl.add_argument("--keyword", help="Search a specific keyword")
    dl.add_argument("--url", help="Download a specific URL")
    dl.add_argument(
        "--max-per-keyword", type=int, default=10, help="Max videos per keyword"
    )
    dl.add_argument("--browser", help="Browser for cookies (overrides project.yaml)")
    dl.add_argument("--no-cookies", action="store_true", help="Skip cookie auth")
    dl.add_argument(
        "--links-only",
        action="store_true",
        help="Save only video links and metadata without downloading video files",
    )

    # status
    sub.add_parser("status", help="Show collection progress")

    # review
    rv = sub.add_parser("review", help="Launch video review UI")
    rv.add_argument("--port", type=int, default=8765, help="Server port")

    # dedup
    sub.add_parser("dedup", help="Deduplicate references CSV")

    # clean
    sub.add_parser(
        "clean", help="Move accepted/rejected videos or sync status link files"
    )

    # export
    exp = sub.add_parser(
        "export", help="Export accepted videos/links to an external dataset folder"
    )
    exp.add_argument("--dest", required=True, help="Destination directory")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    config = cfg.load_config(args.config)

    commands = {
        "init": cmd_init,
        "download": cmd_download,
        "status": cmd_status,
        "review": cmd_review,
        "dedup": cmd_dedup,
        "clean": cmd_clean,
        "export": cmd_export,
    }

    commands[args.command](args, config)


if __name__ == "__main__":
    main()
