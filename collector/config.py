"""
Config loader and validator for project.yaml
"""

import os
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
    if "project" not in raw:
        print(f"[ERROR] Missing required section 'project' in {config_path}")
        sys.exit(1)

    proj = raw["project"]
    for field in ("name", "target_per_class", "resolution", "keywords_file"):
        if field not in proj:
            print(f"[ERROR] Missing 'project.{field}' in config")
            sys.exit(1)

    class_targets = proj.get("class_targets") or proj.get("bucket_targets") or {}
    exclude_terms = proj.get("exclude_title_terms") or []

    config_dir = os.path.dirname(os.path.abspath(config_path))
    raw_out_dir = proj.get("output_dir", "./data")
    if not os.path.isabs(raw_out_dir):
        output_dir = os.path.normpath(os.path.join(config_dir, raw_out_dir))
    else:
        output_dir = raw_out_dir

    config = {
        "name": proj["name"],
        "description": proj.get("description", ""),
        "links_only": bool(proj.get("links_only", False)),
        "video_only": bool(proj.get("video_only", False)),
        "target_per_class": int(proj["target_per_class"]),
        "class_targets": {k: int(v) for k, v in class_targets.items()},
        "resolution": int(proj["resolution"]),
        "min_duration_seconds": int(proj.get("min_duration_seconds", 0)),
        "max_duration_seconds": int(proj.get("max_duration_seconds", 3600)),
        "exclude_title_terms": [str(t).lower() for t in exclude_terms],
        "browser": proj.get("browser", "chrome"),
        "cookies_file": proj.get("cookies_file", ""),
        "enable_remote_components": bool(proj.get("enable_remote_components", True)),
        "sleep_interval": proj.get("sleep_interval", [5, 15]),
        "output_dir": output_dir,
        "classes": {},
    }

    # Load external keywords file
    keywords_file = proj.get("keywords_file")
    keywords_path = os.path.join(config_dir, keywords_file)

    # Language identifier comes from the keywords filename suffix,
    # e.g. "keywords_en.yaml" -> "en", "keywords_zh.yaml" -> "zh".
    config["language"] = os.path.splitext(os.path.basename(keywords_file))[0][-2:]

    if not os.path.exists(keywords_path):
        print(f"[ERROR] Keywords file not found: {keywords_path}")
        sys.exit(1)

    with open(keywords_path, "r", encoding="utf-8") as f:
        keywords_data = yaml.safe_load(f) or {}

    if not keywords_data:
        print(f"[ERROR] Keywords file is empty: {keywords_path}")
        sys.exit(1)

    # Build classes from keywords file
    for cls_name, kw_list in keywords_data.items():
        if not isinstance(kw_list, list):
            print(f"[ERROR] Keywords for class '{cls_name}' must be a list")
            sys.exit(1)

        config["classes"][cls_name] = {
            "description": "",
            "keywords": kw_list,
            "target": int(
                config["class_targets"].get(cls_name, config["target_per_class"])
            ),
        }

    return config


def get_class_names(config):
    """Return list of class names."""
    return list(config["classes"].keys())


def get_target_for_class(config, class_name):
    """Return target count for a specific class."""
    if class_name in config.get("class_targets", {}):
        return int(config["class_targets"][class_name])
    if (
        class_name in config.get("classes", {})
        and "target" in config["classes"][class_name]
    ):
        return int(config["classes"][class_name]["target"])
    return int(config["target_per_class"])


def get_keywords(config, class_name):
    """Return flattened keyword list for a class."""
    return config["classes"][class_name]["keywords"]


def get_video_format(config):
    """Return yt-dlp format string for the configured resolution."""
    res = config["resolution"]
    if config.get("video_only"):
        return f"bestvideo[height<={res}]"
    return f"bestvideo[height<={res}]+bestaudio/best[height<={res}]"


def get_output_dir(config, class_name, language=None):
    """Return the output directory for a class, scoped to the active or given language."""
    lang = language or config["language"]
    if config.get("links_only"):
        return os.path.join(config["output_dir"], class_name, lang)
    return os.path.join(config["output_dir"], class_name, lang, "Videos")
