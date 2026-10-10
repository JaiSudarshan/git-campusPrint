"""File storage.

If SUPABASE_URL and SUPABASE_SERVICE_KEY are set, files go to a private
Supabase Storage bucket. Otherwise they are saved in ./local_uploads
(handy while developing on your own computer).
"""
import os
from urllib.parse import quote

import requests
from flask import current_app, url_for

LOCAL_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "local_uploads")


def _config():
    return (
        os.environ.get("SUPABASE_URL", "").rstrip("/"),
        os.environ.get("SUPABASE_SERVICE_KEY", ""),
        os.environ.get("SUPABASE_BUCKET", "uploads"),
    )


def using_supabase():
    url, key, _ = _config()
    return bool(url and key)


def _headers(extra=None):
    _, key, _ = _config()
    headers = {"apikey": key}
    if key:
        headers["Authorization"] = f"Bearer {key}"
    if extra:
        headers.update(extra)
    return headers


def _local_path(key):
    return os.path.join(LOCAL_DIR, *key.split("/"))


def save(key, data, content_type):
    if using_supabase():
        url, _, bucket = _config()
        resp = requests.post(
            f"{url}/storage/v1/object/{bucket}/{quote(key)}",
            data=data,
            headers=_headers({"Content-Type": content_type, "x-upsert": "false"}),
            timeout=60,
        )
        if not resp.ok:
            raise RuntimeError(f"Storage upload failed ({resp.status_code}): {resp.text[:200]}")
        return
    path = _local_path(key)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as fh:
        fh.write(data)


def delete_many(keys):
    """Best-effort cleanup, used when an order fails halfway."""
    if not keys:
        return
    try:
        if using_supabase():
            url, _, bucket = _config()
            requests.delete(
                f"{url}/storage/v1/object/{bucket}",
                json={"prefixes": list(keys)},
                headers=_headers(),
                timeout=30,
            )
        else:
            for key in keys:
                try:
                    os.remove(_local_path(key))
                except OSError:
                    pass
    except Exception:
        current_app.logger.exception("Cleanup of uploaded files failed")


def signed_url(key, expires=300):
    """A temporary link to a private file (valid for `expires` seconds)."""
    if using_supabase():
        url, _, bucket = _config()
        resp = requests.post(
            f"{url}/storage/v1/object/sign/{bucket}/{quote(key)}",
            json={"expiresIn": expires},
            headers=_headers(),
            timeout=15,
        )
        resp.raise_for_status()
        signed = resp.json()["signedURL"]
        if signed.startswith("/storage/v1"):
            return f"{url}{signed}"
        return f"{url}/storage/v1{signed}"
    return url_for("runner_local_file", key=key)
