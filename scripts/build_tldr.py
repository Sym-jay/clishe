#!/usr/bin/env python3
"""
Build tldr.json.gz from a pinned tldr-pages release.

tldr-pages (https://github.com/tldr-pages/tldr) is a community collection of
short, practical command examples, licensed CC BY 4.0. Clishe ships a
compact copy so `explain` and phrase matching work offline for thousands of
commands. What this script changes from the original pages: it keeps only
the English common, linux and osx pages, joins each page's description
into one line, drops the "More information" links, and stores the examples
as [description, command] pairs. Nothing else is altered.

    python3 scripts/build_tldr.py            # writes tldr.json.gz
    python3 scripts/build_tldr.py v2.4       # a different release
"""
import gzip
import io
import json
import re
import sys
import urllib.request
import zipfile
from pathlib import Path

VERSION = "v2.3"
URL = "https://github.com/tldr-pages/tldr/releases/download/{}/tldr-pages.en.zip"
PLATFORMS = ("common", "linux", "osx")
OUT = Path(__file__).resolve().parent.parent / "tldr.json.gz"
EXAMPLE = re.compile(r"^- (.+?):?\n\n`(.+)`$", re.M)


def page(text: str) -> dict:
    summary = " ".join(line[2:].strip() for line in text.splitlines()
                       if line.startswith("> ") and "More information" not in line)
    return {"s": summary, "e": [[d.strip(), c.strip()] for d, c in EXAMPLE.findall(text)]}


def main():
    version = sys.argv[1] if len(sys.argv) > 1 else VERSION
    with urllib.request.urlopen(URL.format(version), timeout=60) as resp:
        archive = zipfile.ZipFile(io.BytesIO(resp.read()))
    data = {"version": version, "source": "https://github.com/tldr-pages/tldr",
            "license": "CC BY 4.0 https://creativecommons.org/licenses/by/4.0/"}
    for platform in PLATFORMS:
        pages = {}
        for name in sorted(archive.namelist()):
            parts = name.split("/")
            if len(parts) == 2 and parts[0] == platform and parts[1].endswith(".md"):
                pages[parts[1][:-3]] = page(archive.read(name).decode("utf-8"))
        data[platform] = pages
    raw = json.dumps(data, separators=(",", ":"), sort_keys=True).encode()
    OUT.write_bytes(gzip.compress(raw, 9, mtime=0))  # mtime=0: same input, same file
    print(f"{OUT.name}: tldr-pages {version}, "
          + ", ".join(f"{len(data[p])} {p}" for p in PLATFORMS)
          + f" pages, {OUT.stat().st_size // 1024} KB")


if __name__ == "__main__":
    main()
