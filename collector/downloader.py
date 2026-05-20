"""
YouTube video download engine using yt-dlp.
"""

import json
import os
import random
import subprocess
import sys
import time

from . import config as cfg
from . import logger


VIDEO_EXTS = (".mp4", ".mkv", ".webm", ".avi")


def _validate_ytdlp_cmd(cmd):
    """Return True if the yt-dlp command runs successfully."""
    try:
        result = subprocess.run(
            [*cmd, "--version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.returncode == 0
    except Exception:
        return False


def _is_bot_blocked(text):
    """Return True if YouTube bot-check is detected in output text."""
    lower = text.lower()
    return "sign in to confirm" in lower and "not a bot" in lower


def _handle_bot_block(result):
    """Exit if yt-dlp output indicates a bot-check block."""
    combined = (result.stderr or "") + "\n" + (result.stdout or "")
    if _is_bot_blocked(combined):
        print("  [ERROR] YouTube blocked the request: sign-in required to confirm you are not a bot.")
        print("  Provide cookies or a cookies file and retry.")
        sys.exit(1)


def _sleep_between(min_seconds, max_seconds):
    """Sleep for a random interval between downloads."""
    if min_seconds is None or max_seconds is None:
        return
    min_s = max(0, float(min_seconds))
    max_s = max(0, float(max_seconds))
    if max_s < min_s:
        max_s = min_s
    if max_s == 0:
        return
    delay = random.uniform(min_s, max_s)
    print(f"  Sleeping {delay:.1f}s...")
    time.sleep(delay)


def _find_ytdlp():
    """Find a usable yt-dlp command."""
    module_cmd = [sys.executable, "-m", "yt_dlp"]
    if _validate_ytdlp_cmd(module_cmd):
        return module_cmd

    print("[ERROR] yt-dlp not found in the active environment.")
    print("  Install it with: pip install yt-dlp")
    sys.exit(1)


YTDLP = None
BROWSER_COOKIES = "chrome"
USE_COOKIES = True
COOKIES_FILE = ""


def init(browser="chrome", no_cookies=False, cookies_file=""):
    """Initialize the downloader."""
    global YTDLP, BROWSER_COOKIES, USE_COOKIES, COOKIES_FILE
    YTDLP = _find_ytdlp()
    BROWSER_COOKIES = browser
    USE_COOKIES = not no_cookies
    COOKIES_FILE = cookies_file or ""


def _ytdlp_cmd():
    """Return yt-dlp command as a list."""
    if isinstance(YTDLP, list):
        return YTDLP
    return [YTDLP]


def _cookie_args():
    """Return cookie CLI args if enabled."""
    if USE_COOKIES:
        if COOKIES_FILE:
            return ["--cookies", COOKIES_FILE]
        return ["--cookies-from-browser", BROWSER_COOKIES]
    return []


def _duration_filter_args(max_duration_seconds):
    """Return yt-dlp args to skip videos longer than max_duration_seconds."""
    if not max_duration_seconds:
        return []
    return ["--match-filter", f"duration <= {int(max_duration_seconds)}"]




def test_cookies():
    """Test cookie extraction. Returns True if OK."""
    if not USE_COOKIES:
        print("  Cookies disabled, skipping test.")
        return True

    if COOKIES_FILE:
        if not os.path.exists(COOKIES_FILE):
            print(f"  [ERROR] Cookies file not found: {COOKIES_FILE}")
            return False
        print(f"  Using cookies file: {COOKIES_FILE}")
        return True

    print(f"  Testing cookie extraction from {BROWSER_COOKIES}...")
    try:
        result = subprocess.run(
            [*_ytdlp_cmd(), "--cookies-from-browser", BROWSER_COOKIES,
             "--dump-json", "--no-download", "--playlist-items", "1",
             "ytsearch1:test"],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode != 0:
            print(f"  [ERROR] Cookie test failed (exit code {result.returncode}).")
            err = result.stderr.strip() or result.stdout.strip()
            if err:
                print(f"  {err.splitlines()[-1]}")
            return False
        if "Could not copy" in result.stderr:
            print(f"  [ERROR] Cookie extraction FAILED from {BROWSER_COOKIES}.")
            print(f"  Make sure {BROWSER_COOKIES} is CLOSED, or use --no-cookies.")
            return False
    except subprocess.TimeoutExpired:
        print("  [WARN] Cookie test timed out, proceeding anyway.")
    print("  Cookies OK.")
    return True


def get_metadata(query_or_url, max_results=10, is_search=True):
    """Fetch video metadata without downloading."""
    target = f"ytsearch{max_results}:{query_or_url}" if is_search else query_or_url
    cmd = [*_ytdlp_cmd(), "--dump-json", "--no-download", *_cookie_args(), target]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        entries = []
        for line in result.stdout.strip().split("\n"):
            if line.strip():
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return entries
    except (subprocess.TimeoutExpired, Exception) as e:
        print(f"  [WARN] Metadata fetch failed: {e}")
        return []


def _list_video_basenames(output_dir):
    """Return a set of video basenames (no extension) under output_dir."""
    basenames = set()
    if not os.path.exists(output_dir):
        return basenames
    for root, dirs, files in os.walk(output_dir):
        dirs[:] = [d for d in dirs if d != "_rejected"]
        for fname in files:
            if fname.lower().endswith(VIDEO_EXTS):
                basenames.add(os.path.splitext(fname)[0])
    return basenames


def _list_video_ids(output_dir):
    """Return a set of video IDs inferred from existing filenames."""
    ids = set()
    for base in _list_video_basenames(output_dir):
        if "_" in base:
            ids.add(base.rsplit("_", 1)[-1])
    return ids


def _video_exists_for_id(output_dir, video_id):
    """Check if a video file exists for the given ID."""
    if not video_id:
        return False
    suffix = f"_{video_id}".lower()
    for base in _list_video_basenames(output_dir):
        if base.lower().endswith(suffix):
            return True
    return False


def download_keyword(config, keyword, class_name, max_downloads=10):
    """Search YouTube and download videos for a keyword."""
    output_dir = cfg.get_output_dir(config, class_name)
    os.makedirs(output_dir, exist_ok=True)

    output_template = os.path.join(output_dir, "%(title).80s_%(id)s.%(ext)s")
    search_query = f"ytsearch{max_downloads}:{keyword}"
    video_format = cfg.get_video_format(config)
    sleep_min, sleep_max = config["sleep_interval"]
    max_duration = config.get("max_duration_seconds", 3600)
    enable_remote = config.get("enable_remote_components", True)

    print(f"\n{'='*60}")
    print(f"  Keyword  : '{keyword}'")
    print(f"  Class    : {class_name}")
    print(f"  Max DL   : {max_downloads}")
    print(f"  Resolution: {config['resolution']}p")
    print(f"  Max duration: {max_duration}s")
    print(f"  Output   : {output_dir}")
    print(f"{'='*60}")

    existing_ids = _list_video_ids(output_dir)
    entries = get_metadata(keyword, max_downloads, is_search=True)
    if not entries:
        print("  [WARN] No metadata results. Skipping download.")
        return 0

    candidates = []
    for entry in entries:
        vid = entry.get("id")
        url = entry.get("webpage_url") or entry.get("url")
        if not vid or not url:
            continue
        if vid in existing_ids:
            continue
        candidates.append(entry)
        if len(candidates) >= max_downloads:
            break

    if not candidates:
        print("  No new videos to download (all results already present).")
        return 0

    print(f"  Downloading {len(candidates)} new videos...")
    new_videos = 0
    for idx, entry in enumerate(candidates, 1):
        url = entry.get("webpage_url") or entry.get("url")
        print(f"  [{idx}/{len(candidates)}] {url}")
        cmd = [
            *_ytdlp_cmd(),
            "-o", output_template,
            "--restrict-filenames",
            "--no-playlist",
            "--format", video_format,
            "--format-sort", "res,ext",
            "--merge-output-format", "mp4",
            "--no-overwrites",
            *_cookie_args(),
            *_duration_filter_args(max_duration),
            url,
        ]
        if enable_remote:
            cmd += ["--remote-components", "ejs:github"]

        result = subprocess.run(cmd)
        _handle_bot_block(result)

        if _video_exists_for_id(output_dir, entry.get("id")):
            logger.log_entries(config, class_name, [entry], keyword)
            new_videos += 1
            existing_ids.add(entry.get("id"))
        else:
            print("  [WARN] Download failed or was skipped.")

        if idx < len(candidates):
            _sleep_between(sleep_min, sleep_max)

    print(f"  Done. +{new_videos} new videos")
    return new_videos


def download_url(config, url, class_name):
    """Download a specific video by URL."""
    output_dir = cfg.get_output_dir(config, class_name)
    os.makedirs(output_dir, exist_ok=True)

    output_template = os.path.join(output_dir, "%(title).80s_%(id)s.%(ext)s")
    video_format = cfg.get_video_format(config)
    max_duration = config.get("max_duration_seconds", 3600)
    enable_remote = config.get("enable_remote_components", True)

    print(f"\n  Downloading URL: {url}")
    print(f"  Class: {class_name}")
    print(f"  Max duration: {max_duration}s")

    entries = get_metadata(url, is_search=False)
    if not entries:
        print("  [WARN] No metadata for URL. Skipping download.")
        return 0

    entry = entries[0]
    vid = entry.get("id")
    if vid and vid in _list_video_ids(output_dir):
        print("  Already downloaded. Skipping.")
        return 0

    cmd = [
        *_ytdlp_cmd(),
        "-o", output_template,
        "--restrict-filenames",
        "--format", video_format,
        "--format-sort", "res,ext",
        "--merge-output-format", "mp4",
        "--no-overwrites",
        *_cookie_args(),
        *_duration_filter_args(max_duration),
        url,
    ]
    if enable_remote:
        cmd += ["--remote-components", "ejs:github"]

    result = subprocess.run(cmd)
    _handle_bot_block(result)

    if _video_exists_for_id(output_dir, vid):
        logger.log_entries(config, class_name, [entry], url)
        print("  Done. +1 new video")
        return 1

    print("  Done. +0 new videos")
    return 0


def bulk_download(config, class_name, max_per_keyword):
    """Download all keywords for a class."""
    if not test_cookies():
        print("  ABORTING: Fix cookie access or use --no-cookies.")
        sys.exit(1)

    keywords = cfg.get_keywords(config, class_name)
    target = config["target_per_class"]
    existing = logger.count_videos(config, class_name)

    print(f"\n  Bulk Download")
    print(f"  Class: {class_name} | Resolution: {config['resolution']}p")
    print(f"  Current: {existing}/{target} | Keywords: {len(keywords)} | Max/keyword: {max_per_keyword}")
    print(f"  Estimated new downloads: ~{len(keywords) * max_per_keyword}")

    for i, kw in enumerate(keywords, 1):
        print(f"\n  === [{i}/{len(keywords)}] ===")
        download_keyword(config, kw, class_name, max_per_keyword)
        current = logger.count_videos(config, class_name)
        if current >= target:
            print(f"\n  Reached {target} videos for {class_name}! Stopping early.")
            break

    logger.print_progress(config)


