#!/usr/bin/env python3
"""hashsure - one-file, zero-dependency checksum tool.

  python hashsure.py file.zip                      print SHA-256
  python hashsure.py file.zip --expect 9f86d081... verify a download
  python hashsure.py -r dist -o SHA256SUMS         hash a folder into a list
  python hashsure.py --verify SHA256SUMS           check a list of checksums

Algorithms: md5, sha1, sha256 (default), sha512, blake2b.
When verifying, the algorithm is detected from the hash length.
"""
import argparse
import hashlib
import os
import re
import sys

__version__ = "1.0.0"

if os.name == "nt":
    os.system("")
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except Exception:
        pass

USE_COLOR = sys.stdout.isatty() and "NO_COLOR" not in os.environ
ALGOS = ("md5", "sha1", "sha256", "sha512", "blake2b")
BY_LEN = {32: "md5", 40: "sha1", 64: "sha256", 128: "sha512"}
LINE_RE = re.compile(r"^([0-9a-fA-F]{32,128}) [ *](.+)$")


def c(code, text):
    return f"\033[{code}m{text}\033[0m" if USE_COLOR else str(text)


def die(msg):
    sys.stderr.write(f"error: {msg}\n")
    sys.exit(2)


def digest(path, algo):
    h = hashlib.new(algo)
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def algo_for(hexstr, preferred):
    if len(hexstr) == 128 and preferred == "blake2b":
        return "blake2b"
    return BY_LEN.get(len(hexstr))


def collect(paths, recursive, skip=None):
    files = []
    for p in paths:
        if os.path.isdir(p):
            if not recursive:
                sys.stderr.write(f"skipping directory {p} (use -r)\n")
                continue
            for root, dirs, names in os.walk(p):
                dirs.sort()
                for n in sorted(names):
                    files.append(os.path.join(root, n))
        elif os.path.isfile(p):
            files.append(p)
        else:
            die(f"no such file: {p}")
    if skip:
        files = [f for f in files if os.path.abspath(f) != skip]
    return files


def verify_list(sumfile, preferred):
    try:
        with open(sumfile, encoding="utf-8-sig") as f:
            lines = f.read().splitlines()
    except OSError as e:
        die(e.strerror or str(e))
    base = os.path.dirname(os.path.abspath(sumfile))
    total = bad = 0
    for ln in lines:
        m = LINE_RE.match(ln.strip())
        if not m:
            continue
        want, name = m.group(1).lower(), m.group(2)
        total += 1
        algo = algo_for(want, preferred)
        path = os.path.join(base, name)
        if not algo:
            print(c("31", f"BAD LINE  {name} (unknown hash length)"))
            bad += 1
        elif not os.path.isfile(path):
            print(c("33", f"MISSING   {name}"))
            bad += 1
        elif digest(path, algo) == want:
            print(c("32", f"OK        {name}"))
        else:
            print(c("31", f"FAILED    {name}"))
            bad += 1
    if total == 0:
        die("no checksum lines found in " + sumfile)
    print(c("31", f"\n{bad} of {total} failed") if bad else c("32", f"\nall {total} OK"))
    return 1 if bad else 0


def main():
    p = argparse.ArgumentParser(prog="hashsure", description="Hash and verify files.")
    p.add_argument("paths", nargs="*", help="files (or folders with -r)")
    p.add_argument("-a", "--algo", choices=ALGOS, default="sha256")
    p.add_argument("-r", "--recursive", action="store_true", help="hash folders recursively")
    p.add_argument("--expect", metavar="HASH", help="verify one file against this hash")
    p.add_argument("--verify", metavar="SUMFILE", help="check files listed in a checksum file")
    p.add_argument("-o", "--output", metavar="FILE", help="write 'hash  name' lines to FILE")
    p.add_argument("-V", "--version", action="version", version=__version__)
    a = p.parse_args()

    if a.verify:
        return verify_list(a.verify, a.algo)
    if not a.paths:
        die("give at least one file, or use --verify SUMFILE")
    skip = os.path.abspath(a.output) if a.output else None
    files = collect(a.paths, a.recursive, skip)
    if not files:
        die("nothing to hash")

    if a.expect:
        if len(files) != 1:
            die("--expect works with exactly one file")
        want = a.expect.strip().lower()
        if not re.fullmatch(r"[0-9a-f]+", want):
            die("--expect must be a hex string")
        algo = algo_for(want, a.algo)
        if not algo:
            die("can't tell the algorithm from that hash length (32/40/64/128 hex chars)")
        try:
            got = digest(files[0], algo)
        except OSError as e:
            die(e.strerror or str(e))
        if got == want:
            print(c("32", f"OK  {files[0]} ({algo})"))
            return 0
        print(c("31", f"FAILED  {files[0]} ({algo})"))
        print(f"  expected {want}\n  got      {got}")
        return 1

    lines, errors = [], 0
    for f in files:
        try:
            d = digest(f, a.algo)
        except OSError as e:
            sys.stderr.write(f"{f}: {e.strerror}\n")
            errors += 1
            continue
        lines.append(f"{d}  {f.replace(os.sep, '/')}")
    if a.output:
        with open(a.output, "w", encoding="utf-8", newline="\n") as out:
            out.write("\n".join(lines) + ("\n" if lines else ""))
        sys.stderr.write(f"wrote {len(lines)} checksum(s) to {a.output}\n")
    else:
        print("\n".join(lines))
    return 1 if errors else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except BrokenPipeError:
        pass
    except KeyboardInterrupt:
        sys.exit(130)
