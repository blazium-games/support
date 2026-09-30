"""Validates the GitHub issue forms and template chooser config.

Set GITHUB_REPOSITORY (and GITHUB_TOKEN) to also check that every label a form
applies exists in that repository. CI sets both; locally the check is skipped.
"""

import json
import os
import pathlib
import re
import sys
import urllib.request

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[2]
TEMPLATES = ROOT / ".github" / "ISSUE_TEMPLATE"
TYPES = {"markdown", "textarea", "input", "dropdown", "checkboxes"}
ID_RE = re.compile(r"^[a-z][a-z0-9-]*$")
errors = []


def fail(path, msg):
    errors.append(f"{path.relative_to(ROOT).as_posix()}: {msg}")


def repo_labels():
    repo = os.environ.get("GITHUB_REPOSITORY")
    if not repo:
        return None
    headers = {"Accept": "application/vnd.github+json"}
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    names, page = set(), 1
    while True:
        url = f"https://api.github.com/repos/{repo}/labels?per_page=100&page={page}"
        with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=30) as resp:
            batch = json.load(resp)
        names.update(label["name"] for label in batch)
        if len(batch) < 100:
            return names
        page += 1


def check_labels(path, data, known):
    labels = data.get("labels")
    if labels is None:
        return
    if not isinstance(labels, list) or not all(isinstance(l, str) and l.strip() for l in labels):
        fail(path, "labels must be a list of non-empty strings")
        return
    if len(set(labels)) != len(labels):
        fail(path, "labels has duplicates")
    if known is not None:
        for label in labels:
            if label not in known:
                fail(path, f"label {label!r} does not exist in the repository")


def check_form(path, data, known_labels):
    for key in ("name", "description", "body"):
        if not data.get(key):
            fail(path, f'missing "{key}"')
    check_labels(path, data, known_labels)
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
        if kind == "dropdown":
            options = [str(o) for o in attrs.get("options") or []]
            if len(set(options)) != len(options):
                fail(path, f"body[{i}]: dropdown options have duplicates")
        item_id = item.get("id")
        if not item_id:
            fail(path, f"body[{i}]: {kind} needs an id")
            continue
        if not ID_RE.match(str(item_id)):
            fail(path, f"body[{i}]: id {item_id!r} must be lowercase letters, digits, and hyphens")
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
known_labels = repo_labels()
if known_labels is None:
    print("GITHUB_REPOSITORY not set; skipping the label existence check.")
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
        check_form(path, data, known_labels)

if errors:
    print(f"Issue form check failed with {len(errors)} error(s):")
    for e in errors:
        print(f"  - {e}")
    sys.exit(1)
print(f"Issue forms OK ({len(files)} files).")
