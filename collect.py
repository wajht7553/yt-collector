#!/usr/bin/env python3
"""Collect, review, and export YouTube links."""

import argparse
import random
import re
import time

from collector import accepted_downloads, catalog, config as cfg, exporter, search
from collector.reviewer import server


def cmd_collect(args, config, db):
    if args.cls and args.cls not in config["classes"]:
        raise ValueError(f"Unknown class: {args.cls}")
    if args.all and (args.keyword or args.url):
        raise ValueError("Use --class with --keyword or --url")
    if args.url:
        video_id = search.video_id_from_url(args.url)
        if not video_id:
            raise ValueError("Provide a YouTube video URL")
        entries = search.get_metadata(
            config, search.watch_url(video_id), browser=args.browser, no_cookies=args.no_cookies
        )
        videos = search.candidates(config, entries, args.cls, args.url, only_id=video_id)
        print(f"Saved {catalog.save_videos(db, videos)} new links for {args.cls}.")
        return

    class_names = cfg.get_class_names(config) if args.all else [args.cls]
    language = config["language"]
    target = config["target_per_class"]
    minimum, maximum = config["sleep_interval"]
    already_searched = False
    for class_name in class_names:
        keywords = [args.keyword] if args.keyword else cfg.get_keywords(config, class_name)
        for keyword in keywords:
            quota = None
            if not args.keyword:
                if catalog.count_active(db, class_name, language) >= target:
                    break
                quota = (class_name, language, target)
            if already_searched and maximum > 0:
                time.sleep(random.uniform(minimum, maximum))
            print(f"Searching {class_name} [{language}]: {keyword}")
            entries = search.get_metadata(
                config, f"ytsearch{args.max_per_keyword}:{keyword}",
                browser=args.browser, no_cookies=args.no_cookies,
            )
            videos = search.candidates(config, entries, class_name, keyword)
            print(f"  Saved {catalog.save_videos(db, videos, quota=quota)} new links.")
            already_searched = True


def cmd_status(config, db):
    counts = catalog.progress(db)
    for class_name in cfg.get_class_names(config):
        counts.setdefault((class_name, config["language"]), dict.fromkeys(catalog.STATUSES, 0))
    print(f"{config['name']} collection progress")
    for (class_name, language), statuses in sorted(counts.items()):
        collected = statuses["pending"] + statuses["accepted"]
        details = ", ".join(f"{count} {status}" for status, count in statuses.items())
        print(f"  {class_name} [{language}]: {collected}/{config['target_per_class']} ({details})")


def language_code(value):
    if not re.fullmatch(r"[a-zA-Z]{2}|--", value):
        raise argparse.ArgumentTypeError("Use a two-letter language code such as en or ko")
    return value.lower()


def positive_int(value):
    number = int(value)
    if number <= 0:
        raise argparse.ArgumentTypeError("Use an integer greater than zero")
    return number


def main():
    parser = argparse.ArgumentParser(description="YouTube Link Collection Toolkit")
    parser.add_argument("--config", default="project.yaml", help="Path to project config")
    commands = parser.add_subparsers(dest="command", help="Available commands")
    commands.add_parser("init", help="Create the link catalog")

    collect = commands.add_parser(
        "collect", aliases=["download"], help="Save YouTube links and metadata"
    )
    classes = collect.add_mutually_exclusive_group(required=True)
    classes.add_argument("--class", dest="cls", help="Target class")
    classes.add_argument("--all", action="store_true", help="Collect for all configured classes")
    source = collect.add_mutually_exclusive_group()
    source.add_argument("--keyword", help="Search for a specific keyword")
    source.add_argument("--url", help="Save a specific YouTube video URL")
    collect.add_argument("--max-per-keyword", type=positive_int, default=10, help="Results per keyword")
    collect.add_argument("--browser", help="Browser for cookies (overrides project.yaml)")
    collect.add_argument("--no-cookies", action="store_true", help="Skip cookie authentication")

    commands.add_parser("status", help="Show saved links and review progress")
    review = commands.add_parser("review", help="Open the link review UI")
    review.add_argument("--port", type=int, default=8765, help="Server port")
    review.add_argument("--language", type=language_code, help="Load only this collection language")

    export = commands.add_parser("export", help="Export accepted links and metadata to CSV")
    export.add_argument("--dest", required=True, help="Destination directory")
    download_accepted = commands.add_parser(
        "download-accepted", help="Export accepted links and download their videos"
    )
    download_accepted.add_argument(
        "--dest", default="./exported_data",
        help="Destination directory (default: ./exported_data)",
    )
    commands.add_parser("dedup", help="Explain automatic link deduplication")
    commands.add_parser("clean", help="Explain how link review decisions are applied")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return

    config = cfg.load_config(args.config)
    if args.command == "review":
        server.serve(config, port=args.port, language=args.language)
        return

    try:
        with catalog.connect(config) as db:
            if args.command == "init":
                print(f"Link catalog ready in {config['output_dir']}.")
            elif args.command in ("collect", "download"):
                cmd_collect(args, config, db)
            elif args.command == "status":
                cmd_status(config, db)
            elif args.command == "export":
                path, count = exporter.export_dataset(db, args.dest)
                print(f"Exported {count} accepted links to {path}")
            elif args.command == "download-accepted":
                videos = catalog.list_videos(db, status="accepted")
                path = exporter.write_accepted_csv(videos, args.dest)
                print(f"Exported {len(videos)} accepted entries to {path}", flush=True)
                accepted_downloads.download(config, videos, path.parent / "videos")
            elif args.command == "dedup":
                print("The catalog deduplicates links by class, language, and YouTube video ID.")
            elif args.command == "clean":
                print("Review decisions take effect as soon as they are saved.")
    except (RuntimeError, ValueError) as exc:
        parser.exit(1, f"[ERROR] {exc}\n")


if __name__ == "__main__":
    main()
