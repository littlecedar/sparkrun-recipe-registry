#!/usr/bin/env python3
"""Run ComfyUI as a child, prefixing every stdout/stderr chunk with a wall
clock. Splits on both \\n and \\r so tqdm progress-bar updates land as their
own timestamped segments (the whole point: the sampler bars are otherwise
merged into one line and useless for a stage split)."""
import subprocess
import sys
import time

args = [sys.executable, "-u", "main.py", "--listen", "127.0.0.1", "--port", "8188"]
p = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, bufsize=0)
buf = b""
try:
    while True:
        ch = p.stdout.read(1)
        if not ch:
            break
        buf += ch
        if ch in (b"\r", b"\n"):
            seg = buf.decode("utf-8", "replace").strip()
            if seg:
                sys.stdout.write(f"{time.time():.6f} {seg}\n")
                sys.stdout.flush()
            buf = b""
        elif len(buf) > 8192:
            sys.stdout.write(f"{time.time():.6f} PARTIAL {buf.decode('utf-8','replace')}\n")
            sys.stdout.flush()
            buf = b""
finally:
    if buf:
        sys.stdout.write(f"{time.time():.6f} {buf.decode('utf-8','replace')}\n")
    p.wait()
