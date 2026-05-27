#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# ///
"""
web2pdf.py — render a URL to PDF via a throwaway Gotenberg container.

Usage:
    ./web2pdf.py <url> [output.pdf]

If output.pdf is omitted, the file is named YYYY-MM-DD-<url-slug>.pdf,
where the slug is the URL's domain + path with non-alphanumerics
replaced by '-'.

Environment:
    WAIT_DELAY  How long Gotenberg waits after page load before printing.
                Default 5s. Bump for slow / JS-heavy pages (e.g. 15s).

Requirements: docker. (Python stdlib only.)
"""

import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid
from datetime import date


def slugify(url: str) -> str:
    stripped = re.sub(r"^https?://", "", url)
    dashed = re.sub(r"[^a-zA-Z0-9]+", "-", stripped)
    return re.sub(r"^-+|-+$", "", dashed).lower()


def multipart(fields: dict[str, str]) -> tuple[bytes, str]:
    boundary = uuid.uuid4().hex
    parts = []
    for name, value in fields.items():
        parts.append(f"--{boundary}\r\n".encode())
        parts.append(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode())
        parts.append(value.encode())
        parts.append(b"\r\n")
    parts.append(f"--{boundary}--\r\n".encode())
    return b"".join(parts), f"multipart/form-data; boundary={boundary}"


def main() -> int:
    if len(sys.argv) < 2 or len(sys.argv) > 3:
        print("usage: web2pdf.py <url> [output.pdf]", file=sys.stderr)
        return 2

    url = sys.argv[1]
    out = sys.argv[2] if len(sys.argv) == 3 else f"{date.today().isoformat()}-{slugify(url)}.pdf"
    wait_delay = os.environ.get("WAIT_DELAY", "5s")

    cid = subprocess.check_output(
        ["docker", "run", "--rm", "-d", "-p", "3000", "gotenberg/gotenberg:8"],
        text=True,
    ).strip()
    try:
        port_line = subprocess.check_output(
            ["docker", "port", cid, "3000/tcp"], text=True
        ).splitlines()[0]
        port = port_line.rsplit(":", 1)[-1]
        base = f"http://localhost:{port}"

        for _ in range(60):
            try:
                with urllib.request.urlopen(f"{base}/health", timeout=1) as r:
                    if r.status == 200:
                        break
            except (urllib.error.URLError, ConnectionError):
                pass
            time.sleep(0.5)

        body, content_type = multipart({"url": url, "waitDelay": wait_delay})
        req = urllib.request.Request(
            f"{base}/forms/chromium/convert/url",
            data=body,
            headers={"Content-Type": content_type},
        )
        with urllib.request.urlopen(req) as resp, open(out, "wb") as f:
            f.write(resp.read())
    finally:
        subprocess.run(["docker", "stop", cid], stdout=subprocess.DEVNULL, check=False)

    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
