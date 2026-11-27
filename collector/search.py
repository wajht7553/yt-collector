"""Find YouTube videos and extract metadata without downloading media."""

import json
import re
import subprocess
import sys
from urllib.parse import parse_qs, urlsplit


YOUTUBE_HOSTS = {"youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com"}


def valid_id(video_id):
    return isinstance(video_id, str) and re.fullmatch(r"[\w-]{11}", video_id, re.ASCII) is not None


def video_id_from_url(url):
    try:
        parsed = urlsplit(url)
    except ValueError:
        return None
    if parsed.scheme not in ("http", "https"):
        return None
    parts = parsed.path.strip("/").split("/")
    if parsed.hostname == "youtu.be":
        video_id = parts[0]
    elif parsed.hostname in YOUTUBE_HOSTS:
        if parts == ["watch"]:
            video_id = parse_qs(parsed.query).get("v", [""])[0]
        elif len(parts) == 2 and parts[0] in ("shorts", "live", "embed"):
            video_id = parts[1]
        else:
            return None
    else:
        return None
    return video_id if valid_id(video_id) else None


def watch_url(video_id):
    return f"https://www.youtube.com/watch?v={video_id}"


def get_metadata(config, target, *, browser=None, no_cookies=False):
    cmd = [
        sys.executable, "-m", "yt_dlp", "--ignore-config", "--no-cache-dir",
        "--simulate", "--dump-json", "--encoding", "utf-8", "--no-playlist",
        "--ignore-no-formats-error",
    ]
    if not no_cookies:
        if config["cookies_file"]:
            cmd += ["--cookies", config["cookies_file"]]
        else:
            cmd += ["--cookies-from-browser", browser or config["browser"]]
    if config["enable_remote_components"]:
        cmd += ["--remote-components", "ejs:github"]
    cmd += ["--", target]

    try:
        result = subprocess.run(
            cmd, capture_output=True, encoding="utf-8", errors="replace", timeout=120
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RuntimeError(f"Could not fetch YouTube metadata: {exc}") from exc

    entries = []
    for line in result.stdout.splitlines():
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(entry, dict):
            entries.append(entry)
    if result.returncode:
        error = result.stderr.strip() or f"yt-dlp exited with code {result.returncode}"
        if not entries:
            raise RuntimeError(error)
        print(f"[WARN] yt-dlp returned partial results.\n{error}", file=sys.stderr)
    return entries


def candidates(config, entries, class_name, keyword, *, only_id=None):
    max_duration = config["max_duration_seconds"]
    for entry in entries:
        video_id = entry.get("id")
        if not valid_id(video_id) or (only_id is not None and video_id != only_id):
            continue
        duration = entry.get("duration")
        if max_duration and isinstance(duration, (int, float)) and duration > max_duration:
            continue
        yield {
            "class_name": class_name,
            "language": config["language"],
            "video_id": video_id,
            "title": entry.get("title"),
            "channel": entry.get("channel") or entry.get("uploader"),
            "duration": duration,
            "license": entry.get("license"),
            "keywords": (keyword,),
        }
