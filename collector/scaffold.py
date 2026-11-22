"""
Folder structure scaffolding from project config
"""

import os


def scaffold(config):
    """Create the per-language folder tree for every class in the active keywords file."""
    output_dir = config["output_dir"]
    classes = config["classes"]
    language = config["language"]
    links_only = config.get("links_only", False)

    created = []
    os.makedirs(output_dir, exist_ok=True)

    for cls_name in classes:
        if links_only:
            lang_dir = os.path.join(output_dir, cls_name, language)
            if not os.path.exists(lang_dir):
                os.makedirs(lang_dir, exist_ok=True)
                created.append(lang_dir)
            links_file = os.path.join(lang_dir, "links.txt")
            if not os.path.exists(links_file):
                with open(links_file, "w", encoding="utf-8") as f:
                    pass
                created.append(links_file)
        else:
            vid_dir = os.path.join(output_dir, cls_name, language, "Videos")
            if not os.path.exists(vid_dir):
                os.makedirs(vid_dir, exist_ok=True)
                created.append(vid_dir)

    # Create tracking files if they don't exist
    for fname in ("source_references.csv", "review_decisions.json"):
        fpath = os.path.join(output_dir, fname)
        if not os.path.exists(fpath):
            if fname.endswith(".csv"):
                with open(fpath, "w", encoding="utf-8", newline="") as f:
                    f.write(
                        "Class,Language,Video_ID,Source_URL,Date_Accessed,License,"
                        "Keyword,Title,Channel,Duration\n"
                    )
            elif fname.endswith(".json"):
                with open(fpath, "w", encoding="utf-8") as f:
                    f.write("{}")
            created.append(fpath)

    return created


def print_tree(config):
    """Print the folder tree that will be created."""
    output_dir = config["output_dir"]
    classes = config["classes"]
    language = config["language"]
    leaf = "links.txt" if config.get("links_only") else "Videos/"

    print(f"\n  {output_dir}/")
    cls_list = list(classes.keys())
    for i, cls_name in enumerate(cls_list):
        is_last = i == len(cls_list) - 1
        prefix = "  +-- " if is_last else "  |-- "
        child_prefix = "      " if is_last else "  |   "
        print(f"{prefix}{cls_name}/")
        print(f"{child_prefix}+-- {language}/")
        print(f"{child_prefix}    +-- {leaf}")
