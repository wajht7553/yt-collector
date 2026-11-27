"""
Config loader and validator for project.yaml
"""

import os
import re
import sys
import yaml


def load_config(config_path="project.yaml"):
    """Load and validate the project configuration. Classes are derived from the keywords file specified in project config."""
    if not os.path.exists(config_path):
        print(f"[ERROR] Config file not found: {config_path}")
        print("  Create a project.yaml or specify path with --config")
        sys.exit(1)

    with open(config_path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    # Validate required sections
    if not isinstance(raw, dict) or not isinstance(raw.get("project"), dict):
        print(f"[ERROR] Missing required section 'project' in {config_path}")
        sys.exit(1)

    proj = raw["project"]
    for field in ("name", "target_per_class", "keywords_file"):
        if field not in proj:
            print(f"[ERROR] Missing 'project.{field}' in config")
            sys.exit(1)

    min_sleep, max_sleep = proj.get("sleep_interval", [5, 15])
    if min_sleep is None or max_sleep is None:
        sleep_interval = (0, 0)
    else:
        min_sleep = max(0, float(min_sleep))
        sleep_interval = (min_sleep, max(min_sleep, float(max_sleep)))

    config = {
        "name": proj["name"],
        "description": proj.get("description", ""),
        "target_per_class": int(proj["target_per_class"]),
        "max_duration_seconds": int(proj.get("max_duration_seconds", 3600)),
        "browser": proj.get("browser", "chrome"),
        "cookies_file": proj.get("cookies_file", ""),
        "enable_remote_components": bool(proj.get("enable_remote_components", True)),
        "sleep_interval": sleep_interval,
        "output_dir": proj.get("output_dir", "./data"),
        "classes": {},
    }

    # Load external keywords file
    keywords_file = proj.get("keywords_file")
    config_dir = os.path.dirname(os.path.abspath(config_path))
    keywords_path = os.path.join(config_dir, keywords_file)

    # Language identifier comes from the keywords filename suffix,
    # e.g. "keywords_en.yaml" -> "en", "keywords_zh.yaml" -> "zh".
    stem = os.path.splitext(os.path.basename(keywords_file))[0]
    match = re.fullmatch(r"keywords_([a-zA-Z]{2}|--)", stem)
    if not match:
        print("[ERROR] Name the keyword file keywords_<language>.yaml")
        sys.exit(1)
    config["language"] = match.group(1).lower()

    if not os.path.exists(keywords_path):
        print(f"[ERROR] Keywords file not found: {keywords_path}")
        sys.exit(1)

    with open(keywords_path, "r", encoding="utf-8") as f:
        keywords_data = yaml.safe_load(f) or {}

    if not isinstance(keywords_data, dict) or not keywords_data:
        print(f"[ERROR] Keywords file must contain a class-to-keywords mapping: {keywords_path}")
        sys.exit(1)

    # Build classes from keywords file
    for cls_name, kw_list in keywords_data.items():
        if not isinstance(cls_name, str) or not cls_name.strip():
            print("[ERROR] Class names must be nonempty strings")
            sys.exit(1)
        if not isinstance(kw_list, list) or not all(
            isinstance(keyword, str) and keyword.strip() for keyword in kw_list
        ):
            print(f"[ERROR] Keywords for class '{cls_name}' must be a list of nonempty strings")
            sys.exit(1)

        config["classes"][cls_name] = {
            "description": "",  # No description in keywords file
            "keywords": kw_list,
        }

    return config


def get_class_names(config):
    """Return list of class names."""
    return list(config["classes"].keys())


def get_keywords(config, class_name):
    """Return flattened keyword list for a class."""
    return config["classes"][class_name]["keywords"]
