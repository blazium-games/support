"""Validates the GitHub issue forms and template chooser config."""

import pathlib
import sys

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[2]
TEMPLATES = ROOT / ".github" / "ISSUE_TEMPLATE"
TYPES = {"markdown", "textarea", "input", "dropdown", "checkboxes"}
errors = []


def fail(path, msg):
    errors.append(f"{path.relative_to(ROOT).as_posix()}: {msg}")


def check_form(path, data):
    for key in ("name", "description", "body"):
        if not data.get(key):
            fail(path, f'missing "{key}"')
    ids = set()
    for i, item in enumerate(data.get("body") or []):
        kind = item.get("type")
        if kind not in TYPES:
            fail(path, f"body[{i}]: unknown type {kind!r}")
            continue
        attrs = item.get("attributes") or {}
        if kind == "markdown":
            if not attrs.get("value"):
                fail(path, f"body[{i}]: markdown needs attributes.value")
            continue
        if not attrs.get("label"):
            fail(path, f"body[{i}]: {kind} needs attributes.label")
        if kind in ("dropdown", "checkboxes") and not attrs.get("options"):
            fail(path, f"body[{i}]: {kind} needs attributes.options")
        item_id = item.get("id")
        if item_id:
            if item_id in ids:
                fail(path, f"body[{i}]: duplicate id {item_id!r}")
            ids.add(item_id)


def check_config(path, data):
    if not isinstance(data.get("blank_issues_enabled"), bool):
        fail(path, "blank_issues_enabled must be true or false")
    for i, link in enumerate(data.get("contact_links") or []):
        for key in ("name", "url", "about"):
            if not link.get(key):
                fail(path, f"contact_links[{i}]: missing {key}")
        if link.get("url") and not str(link["url"]).startswith(("https://", "mailto:")):
            fail(path, f"contact_links[{i}]: url must be https or mailto")


files = sorted(TEMPLATES.glob("*.yml")) + sorted(TEMPLATES.glob("*.yaml"))
if not files:
    errors.append(".github/ISSUE_TEMPLATE: no templates found")
for path in files:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as err:
        fail(path, f"invalid YAML ({err})")
        continue
    if not isinstance(data, dict):
        fail(path, "must be a mapping")
    elif path.stem == "config":
        check_config(path, data)
    else:
        check_form(path, data)

if errors:
    print(f"Issue form check failed with {len(errors)} error(s):")
    for e in errors:
        print(f"  - {e}")
    sys.exit(1)
print(f"Issue forms OK ({len(files)} files).")
