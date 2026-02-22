import base64, json, os, time, urllib.request, urllib.error
from datetime import datetime, timezone

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
GITHUB_REPO  = os.environ.get("GITHUB_REPO", "carolinejnovak-source/personal-spending")
DATA_FILE    = "data/transactions.json"
CACHE_TTL    = 30  # seconds

_cache = {"data": None, "sha": None, "at": 0}


def _headers():
    return {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "personal-spending-app",
    }


def get_data(force=False):
    global _cache
    if not force and _cache["data"] is not None and time.time() - _cache["at"] < CACHE_TTL:
        return _cache["data"], _cache["sha"]

    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{DATA_FILE}"
    req = urllib.request.Request(url, headers=_headers())
    try:
        with urllib.request.urlopen(req) as r:
            res = json.loads(r.read())
            content = base64.b64decode(res["content"].replace("\n", "")).decode()
            data = json.loads(content)
            _cache = {"data": data, "sha": res["sha"], "at": time.time()}
            return data, res["sha"]
    except urllib.error.HTTPError as e:
        if e.code == 404:
            empty = {"transactions": []}
            _cache = {"data": empty, "sha": None, "at": time.time()}
            return empty, None
        raise


def save_data(data, sha=None):
    global _cache
    url     = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{DATA_FILE}"
    content = base64.b64encode(json.dumps(data, indent=2).encode()).decode()
    body    = {
        "message": f"Update transactions {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        "content": content,
    }
    if sha:
        body["sha"] = sha

    req = urllib.request.Request(
        url, data=json.dumps(body).encode(), method="PUT",
        headers={**_headers(), "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req) as r:
        res = json.loads(r.read())
        new_sha = res["content"]["sha"]
        _cache  = {"data": data, "sha": new_sha, "at": time.time()}
        return new_sha
