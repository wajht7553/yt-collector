"""
Folder structure scaffolding from project config.
"""

import os


def scaffold(config):
    """Create the full folder tree based on project config."""
    output_dir = config["output_dir"]
    classes = config["classes"]

    created = []

    for cls_name in classes:
        vid_dir = os.path.join(output_dir, cls_name, "Videos")
        os.makedirs(vid_dir, exist_ok=True)
        created.append(vid_dir)

    # Create tracking files if they don't exist
    for fname in ("source_references.csv", "review_decisions.json"):
        fpath = os.path.join(output_dir, fname)
        if not os.path.exists(fpath):
            if fname.endswith(".csv"):
                with open(fpath, "w", encoding="utf-8", newline="") as f:
                    f.write(
                        "Class,Source_URL,Source_Type,Media_Type,"
                        "Num_Videos,Date_Accessed,License,Notes\n"
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

    print(f"\n  {output_dir}/")
    cls_list = list(classes.keys())
    for i, cls_name in enumerate(cls_list):
        is_last = i == len(cls_list) - 1
        prefix = "  +-- " if is_last else "  |-- "
        child_prefix = "      " if is_last else "  |   "
        print(f"{prefix}{cls_name}/")
        print(f"{child_prefix}+-- Videos/")
