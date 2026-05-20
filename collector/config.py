"""
Config loader and validator for project.yaml.
"""

import os
import sys

import yaml


def load_config(config_path="project.yaml"):
    """Load and validate the project configuration."""
    if not os.path.exists(config_path):
        print(f"[ERROR] Config file not found: {config_path}")
        print("  Create a project.yaml or specify path with --config")
        sys.exit(1)

    with open(config_path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    # Validate required sections
    for key in ("project", "classes"):
        if key not in raw:
            print(f"[ERROR] Missing required section '{key}' in {config_path}")
            sys.exit(1)

    proj = raw["project"]
    for field in ("name", "target_per_class", "resolution"):
        if field not in proj:
            print(f"[ERROR] Missing 'project.{field}' in config")
            sys.exit(1)

    config = {
        "name": proj["name"],
        "description": proj.get("description", ""),
        "target_per_class": int(proj["target_per_class"]),
        "resolution": int(proj["resolution"]),
        "max_duration_seconds": int(proj.get("max_duration_seconds", 3600)),
        "browser": proj.get("browser", "chrome"),
        "cookies_file": proj.get("cookies_file", ""),
        "enable_remote_components": bool(proj.get("enable_remote_components", True)),
        "sleep_interval": proj.get("sleep_interval", [5, 15]),
        "output_dir": proj.get("output_dir", "./data"),
        "classes": {},
    }

    # Parse classes and flatten keyword categories
    for cls_name, cls_data in raw["classes"].items():
        keywords = []
        kw_data = cls_data.get("keywords", {})
        if isinstance(kw_data, dict):
            # Grouped by category - flatten
            for category, kw_list in kw_data.items():
                keywords.extend(kw_list)
        elif isinstance(kw_data, list):
            # Flat list
            keywords = kw_data

        config["classes"][cls_name] = {
            "description": cls_data.get("description", ""),
            "keywords": keywords,
        }

    return config


def get_class_names(config):
    """Return list of class names."""
    return list(config["classes"].keys())


def get_keywords(config, class_name):
    """Return flattened keyword list for a class."""
    return config["classes"][class_name]["keywords"]


def get_video_format(config):
    """Return yt-dlp format string for the configured resolution."""
    res = config["resolution"]
    return f"bestvideo[height<={res}]+bestaudio/best[height<={res}]"


def get_output_dir(config, class_name):
    """Return the output directory for a class."""
    return os.path.join(config["output_dir"], class_name, "Videos")
