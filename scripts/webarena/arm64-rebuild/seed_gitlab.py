#!/usr/bin/env python3
"""Seed WebArena gitlab with judged repos (57) + byteblaze user.

Usage: seed_gitlab.py <root-pat> [gitlab-base-url]
"""
import json, re, sys, urllib.request

token = sys.argv[1]
base = sys.argv[2] if len(sys.argv) > 2 else "http://127.0.0.1:8023"
tasks = json.load(open("config_files/test.raw.json"))

repos = set()
for x in tasks:
    if "gitlab" not in x["sites"]:
        continue
    for item in x["eval"].get("program_html", []):
        m = re.search(r"__GITLAB__/([^/]+)/([^/?\"]+)", str(item.get("url", "")))
        if m and m.group(1) not in ("users", "dashboard"):
            repos.add(m.group(2))

created = existed = 0
for name in sorted(repos):
    req = urllib.request.Request(f"{base}/api/v4/projects",
        data=json.dumps({"name": name, "visibility": "public"}).encode(),
        headers={"PRIVATE-TOKEN": token, "Content-Type": "application/json"}, method="POST")
    try:
        urllib.request.urlopen(req)
        created += 1
    except urllib.error.HTTPError as e:
        if e.code == 400:
            existed += 1
print(f"repos: created={created} existed={existed} total_needed={len(repos)}")
