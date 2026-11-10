"""Pre-download all HF task files into OSWorld's local cache so setup never
hits the network. Run with the same proxy env as the baseline driver."""
import glob, hashlib, json, os, sys, uuid
import requests

domain = sys.argv[1] if len(sys.argv) > 1 else "os"
cache_dir = "cache"
os.makedirs(cache_dir, exist_ok=True)

urls = []
for f in glob.glob(f"evaluation_examples/examples/{domain}/*.json"):
    d = json.load(open(f))
    for c in d.get("config", []):
        if c.get("type") == "download":
            for item in c["parameters"]["files"]:
                urls.append((item["url"], item["path"]))
    ev = d.get("evaluator", {})
    def walk(o):
        if isinstance(o, dict):
            if o.get("type") == "download":
                for item in o["parameters"]["files"]:
                    urls.append((item["url"], item["path"]))
            for v in o.values(): walk(v)
        elif isinstance(o, list):
            for v in o: walk(v)
    walk(ev)

urls = sorted(set(urls))
print(f"{len(urls)} files to cache")
ok = fail = 0
for url, path in urls:
    cache_path = os.path.join(cache_dir, "{:}_{:}".format(
        uuid.uuid5(uuid.NAMESPACE_URL, url), os.path.basename(path)))
    if os.path.exists(cache_path) and os.path.getsize(cache_path) > 0:
        ok += 1
        continue
    try:
        r = requests.get(url, timeout=120, stream=True)
        r.raise_for_status()
        with open(cache_path, "wb") as fh:
            for chunk in r.iter_content(65536):
                fh.write(chunk)
        ok += 1
        print("cached:", os.path.basename(path))
    except Exception as e:
        fail += 1
        print("FAIL:", url[-60:], str(e)[:60])
print(f"done: {ok} cached, {fail} failed")
