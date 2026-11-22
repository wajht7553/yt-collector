"""
YouTube video & link collection engine using yt-dlp
"""

import os
import sys
import json
import time
import random
import subprocess

from . import logger
from . import config as cfg

VIDEO_EXTS = (".mp4", ".mkv", ".webm", ".avi")
YOUTUBE_ID_LENGTH = 11
YTDLP = None
BROWSER_COOKIES = "chrome"
USE_COOKIES = True
COOKIES_FILE = ""


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
    lower = (text or "").lower()
    return "sign in to confirm" in lower and "not a bot" in lower


def _handle_bot_block(result):
    """Exit if yt-dlp output indicates a bot-check block."""
    combined = (result.stderr or "") + "\n" + (result.stdout or "")
    if _is_bot_blocked(combined):
        print(
            "  [ERROR] YouTube blocked the request: sign-in required to confirm you are not a bot."
        )
        print("  Provide cookies or a cookies file and retry.")
        sys.exit(1)


def _sleep_between(min_seconds, max_seconds):
    """Sleep for a random interval between requests."""
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


def init(browser="chrome", no_cookies=False, cookies_file=""):
    """Initialize the downloader."""
    global YTDLP, BROWSER_COOKIES, USE_COOKIES, COOKIES_FILE
    YTDLP = _find_ytdlp()
    BROWSER_COOKIES = browser
    USE_COOKIES = not no_cookies
    COOKIES_FILE = cookies_file or ""


def _ytdlp_cmd():
    """Return yt-dlp command as a list."""
    global YTDLP
    if YTDLP is None:
        YTDLP = _find_ytdlp()
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


def _duration_filter_args(min_duration_seconds, max_duration_seconds):
    """Return yt-dlp args to filter videos by duration."""
    filters = []
    if min_duration_seconds and int(min_duration_seconds) > 0:
        filters.append(f"duration >= {int(min_duration_seconds)}")
    if max_duration_seconds and int(max_duration_seconds) > 0:
        filters.append(f"duration <= {int(max_duration_seconds)}")
    if not filters:
        return []
    return ["--match-filter", " & ".join(filters)]


def test_cookies(links_only=False):
    """Test cookie extraction. Returns True if OK."""
    global USE_COOKIES
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
            [
                *_ytdlp_cmd(),
                "--cookies-from-browser",
                BROWSER_COOKIES,
                "--flat-playlist",
                "--dump-json",
                "--no-download",
                "--playlist-items",
                "1",
                "ytsearch1:test",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        combined = (result.stderr or "") + "\n" + (result.stdout or "")
        if result.returncode != 0 or "Could not copy" in combined:
            if links_only:
                print(
                    f"  [WARN] Could not copy cookies from {BROWSER_COOKIES} (browser may be open)."
                )
                print("  Falling back to --no-cookies for link collection.")
                USE_COOKIES = False
                return True
            print(f"  [ERROR] Cookie extraction FAILED from {BROWSER_COOKIES}.")
            print(f"  Make sure {BROWSER_COOKIES} is CLOSED, or use --no-cookies.")
            return False
    except subprocess.TimeoutExpired:
        print("  [WARN] Cookie test timed out, proceeding anyway.")
    print("  Cookies OK.")
    return True


def get_metadata(query_or_url, max_results=10, is_search=True, flat_search=False):
    """Fetch video metadata without downloading."""
    global USE_COOKIES
    target = f"ytsearch{max_results}:{query_or_url}" if is_search else query_or_url
    mode_args = ["--flat-playlist"] if (is_search and flat_search) else []
    cmd = [
        *_ytdlp_cmd(),
        *mode_args,
        "--dump-json",
        "--no-download",
        *_cookie_args(),
        target,
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=120,
        )
        combined = (result.stderr or "") + "\n" + (result.stdout or "")
        if USE_COOKIES and ("Could not copy" in combined or "PermissionError" in combined):
            USE_COOKIES = False
            cmd = [
                *_ytdlp_cmd(),
                *mode_args,
                "--dump-json",
                "--no-download",
                target,
            ]
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=120,
            )

        entries = []
        for line in (result.stdout or "").strip().split("\n"):
            if line.strip():
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return entries
    except (subprocess.TimeoutExpired, Exception) as e:
        print(f"  [WARN] Metadata fetch failed: {e}")
        return []


def get_direct_stream_url(video_url, resolution=720):
    """Resolve a direct playable MP4 stream URL via yt-dlp -g for the Review UI."""
    fmt = f"best[height<={int(resolution)}][ext=mp4]/best[ext=mp4]/best[height<={int(resolution)}]/best"
    cmd = [
        *_ytdlp_cmd(),
        "-g",
        "--no-playlist",
        "-f",
        fmt,
        *_cookie_args(),
        video_url,
    ]
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
        )
        if result.returncode != 0 and USE_COOKIES:
            cmd_no_cookies = [
                *_ytdlp_cmd(),
                "-g",
                "--no-playlist",
                "-f",
                fmt,
                video_url,
            ]
            result = subprocess.run(
                cmd_no_cookies,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=30,
            )
        for line in (result.stdout or "").strip().splitlines():
            if line.strip().startswith("http"):
                return line.strip()
    except Exception:
        pass
    return ""


def _list_video_basenames(output_dir):
    """Return a set of video basenames (no extension) under output_dir."""
    basenames = set()
    if not os.path.exists(output_dir):
        return basenames
    for root, dirs, files in os.walk(output_dir):
        for fname in files:
            if fname.lower().endswith(VIDEO_EXTS):
                basenames.add(os.path.splitext(fname)[0])
    return basenames


def _list_video_ids(output_dir):
    """Return a set of video IDs inferred from existing filenames."""
    ids = set()
    for base in _list_video_basenames(output_dir):
        if len(base) > YOUTUBE_ID_LENGTH and base[-(YOUTUBE_ID_LENGTH + 1)] == "_":
            ids.add(base[-YOUTUBE_ID_LENGTH:])
    return ids


def _existing_video_ids(config, class_name, output_dir):
    """Return video IDs already downloaded, collected, or reviewed."""
    ids = _list_video_ids(output_dir)

    for r in logger.load_all_entries(config):
        if r.get("Video_ID"):
            ids.add(r["Video_ID"])
        elif r.get("Source_URL"):
            ids.add(logger.extract_video_id(r["Source_URL"]))

    decisions = logger.load_decisions(config)
    for rel_path in decisions:
        norm = rel_path.replace("\\", "/")
        base = os.path.splitext(os.path.basename(norm))[0]
        if len(base) == YOUTUBE_ID_LENGTH:
            ids.add(base)
        elif len(base) > YOUTUBE_ID_LENGTH and base[-(YOUTUBE_ID_LENGTH + 1)] == "_":
            ids.add(base[-YOUTUBE_ID_LENGTH:])

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


def _is_excluded_entry(entry, config):
    """Return True if the video entry is a live stream or matches configured exclude_title_terms."""
    if entry.get("is_live") or entry.get("live_status") in ("is_live", "is_upcoming"):
        return True
    title = (entry.get("title") or "").lower()
    if not title:
        return False
    for term in config.get("exclude_title_terms") or []:
        if term and term in title:
            return True
    return False


def download_keyword(config, keyword, class_name, max_downloads=10):
    """Search YouTube and collect video links or download video files for a keyword."""
    links_only = config.get("links_only", False)
    output_dir = cfg.get_output_dir(config, class_name)
    os.makedirs(output_dir, exist_ok=True)

    min_duration = config.get("min_duration_seconds", 0)
    max_duration = config.get("max_duration_seconds", 3600)
    sleep_min, sleep_max = config["sleep_interval"]
    enable_remote = config.get("enable_remote_components", True)
    mode_label = (
        "Links Only (no video download)"
        if links_only
        else f"Video Download ({config['resolution']}p)"
    )

    print(f"\n{'='*60}")
    print(f"  Keyword  : '{keyword}'")
    print(f"  Class    : {class_name} ({config['language']})")
    print(f"  Mode     : {mode_label}")
    print(f"  Max      : {max_downloads}")
    if min_duration:
        print(f"  Duration : {min_duration}s - {max_duration}s")
    else:
        print(f"  Max duration: {max_duration}s")
    print(f"  Output   : {output_dir}")
    print(f"{'='*60}")

    existing_ids = _existing_video_ids(config, class_name, output_dir)
    pool_size = max(max_downloads * 3, max_downloads + 15) if links_only else max_downloads
    entries = get_metadata(keyword, pool_size, is_search=True, flat_search=links_only)
    if not entries:
        print("  [WARN] No metadata results. Skipping.")
        return 0

    candidates = []
    for entry in entries:
        vid = entry.get("id") or logger.extract_video_id(
            entry.get("webpage_url") or entry.get("url", "")
        )
        url = logger.normalize_url(
            entry.get("webpage_url") or entry.get("url", ""), vid
        )
        if not vid or not url:
            continue
        if vid in existing_ids:
            continue
        if _is_excluded_entry(entry, config):
            continue

        dur = entry.get("duration")
        if dur is not None:
            try:
                dur_val = float(dur)
                if min_duration and dur_val < min_duration:
                    continue
                if max_duration and dur_val > max_duration:
                    continue
            except (ValueError, TypeError):
                pass
        elif min_duration > 0:
            continue

        entry["id"] = vid
        entry["webpage_url"] = url
        candidates.append(entry)
        existing_ids.add(vid)
        if len(candidates) >= max_downloads:
            break

    if not candidates:
        print("  No new videos to collect (all results already present or filtered).")
        return 0

    if links_only:
        logger.log_entries(config, class_name, candidates, keyword)
        for idx, entry in enumerate(candidates, 1):
            url = entry["webpage_url"]
            title = entry.get("title") or entry["id"]
            dur = entry.get("duration")
            dur_note = f" ({int(dur)}s)" if dur is not None else ""
            print(f"  [{idx}/{len(candidates)}] + {url} | {title[:65]}{dur_note}")
        print(f"  Done. +{len(candidates)} new video links saved.")
        return len(candidates)

    output_template = os.path.join(output_dir, "%(title).80s_%(id)s.%(ext)s")
    video_format = cfg.get_video_format(config)

    print(f"  Downloading {len(candidates)} new videos...")
    new_videos = 0
    for idx, entry in enumerate(candidates, 1):
        url = entry.get("webpage_url") or entry.get("url")
        print(f"  [{idx}/{len(candidates)}] {url}")
        cmd = [
            *_ytdlp_cmd(),
            "-o",
            output_template,
            "--restrict-filenames",
            "--no-playlist",
            "--format",
            video_format,
            "--format-sort",
            "res,ext",
            "--merge-output-format",
            "mp4",
            "--no-overwrites",
            *_cookie_args(),
            *_duration_filter_args(min_duration, max_duration),
            url,
        ]
        if enable_remote:
            cmd += ["--remote-components", "ejs:github"]

        result = subprocess.run(cmd)
        _handle_bot_block(result)

        if _video_exists_for_id(output_dir, entry.get("id")):
            logger.log_entries(config, class_name, [entry], keyword)
            new_videos += 1
        else:
            print("  [WARN] Download failed or was skipped.")

        if idx < len(candidates):
            _sleep_between(sleep_min, sleep_max)

    print(f"  Done. +{new_videos} new videos")
    return new_videos


def download_url(config, url, class_name):
    """Collect a specific video link or download the video file by URL."""
    links_only = config.get("links_only", False)
    output_dir = cfg.get_output_dir(config, class_name)
    os.makedirs(output_dir, exist_ok=True)

    min_duration = config.get("min_duration_seconds", 0)
    max_duration = config.get("max_duration_seconds", 3600)
    enable_remote = config.get("enable_remote_components", True)

    print(f"\n  Processing URL: {url}")
    print(f"  Class: {class_name}")

    existing_ids = _existing_video_ids(config, class_name, output_dir)
    entries = get_metadata(url, is_search=False)
    if not entries:
        print("  [WARN] No metadata for URL. Skipping.")
        return 0

    entry = entries[0]
    vid = entry.get("id") or logger.extract_video_id(url)
    norm_url = logger.normalize_url(
        entry.get("webpage_url") or entry.get("url") or url, vid
    )
    if vid and vid in existing_ids:
        print("  Already collected. Skipping.")
        return 0

    entry["id"] = vid
    entry["webpage_url"] = norm_url

    if links_only:
        logger.log_entries(config, class_name, [entry], url)
        print(f"  Done. +1 new video link saved: {norm_url}")
        return 1

    output_template = os.path.join(output_dir, "%(title).80s_%(id)s.%(ext)s")
    video_format = cfg.get_video_format(config)
    cmd = [
        *_ytdlp_cmd(),
        "-o",
        output_template,
        "--restrict-filenames",
        "--format",
        video_format,
        "--format-sort",
        "res,ext",
        "--merge-output-format",
        "mp4",
        "--no-overwrites",
        *_cookie_args(),
        *_duration_filter_args(min_duration, max_duration),
        norm_url,
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
    """Collect links or download videos for all keywords in a class."""
    links_only = config.get("links_only", False)
    if not test_cookies(links_only=links_only):
        print("  ABORTING: Fix cookie access or use --no-cookies.")
        sys.exit(1)

    keywords = cfg.get_keywords(config, class_name)
    target = cfg.get_target_for_class(config, class_name)
    language = config["language"]
    existing = logger.count_videos(config, class_name, language=language)
    sleep_min, sleep_max = config.get("sleep_interval", [5, 15])
    mode_short = "Links Only" if links_only else f"{config['resolution']}p"

    print(f"\n  Bulk {'Link Collection' if links_only else 'Download'}")
    print(f"  Class: {class_name} | Language: {language} | Mode: {mode_short}")
    print(
        f"  Current: {existing}/{target} | Keywords: {len(keywords)} | Max/keyword: {max_per_keyword}"
    )

    if existing >= target:
        print(f"\n  Already reached target ({existing}/{target}) for {class_name}!")
        logger.print_progress(config)
        return

    for i, kw in enumerate(keywords, 1):
        print(f"\n  === [{i}/{len(keywords)}] ===")
        remaining = max(1, target - existing)
        batch_limit = min(max_per_keyword, remaining) if links_only else max_per_keyword
        download_keyword(config, kw, class_name, batch_limit)
        existing = logger.count_videos(config, class_name, language=language)
        if existing >= target:
            print(f"\n  Reached {target} for {class_name}! Stopping early.")
            break
        if links_only and i < len(keywords):
            _sleep_between(min(sleep_min, 1), min(sleep_max, 3))

    logger.print_progress(config)
