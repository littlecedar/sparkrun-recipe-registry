#!/bin/bash
# SPDX-FileCopyrightText: 2026 ursuciprian (original mod), Andre Knopke (upstream fix), Travis Wichert (port/adaptation)
#
# SPDX-License-Identifier: Apache-2.0
#
# Origin: adapted from mods/sglang-radix-chunked-insert-fix/run.sh in
#         https://github.com/ursuciprian/qwen3.8-flash-next-dgx-spark-tp-2 (Apache-2.0),
#         itself a port of the closed PR sgl-project/sglang#38355 (andreasknopke).
# Changes from the original: added the SPDX/attribution headers above, added a
#         post-write import smoke test so a bad patch fails at hook time rather than
#         nine minutes into a weight load, and made the failure mode explicit. The
#         anchor strings and the substitution logic are unchanged from upstream.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may not use this
# file except in compliance with the License. You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software distributed under
# the License is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF
# ANY KIND, either express or implied. See the License for the specific language
# governing permissions and limitations under the License.
set -euo pipefail

#####################################################################
# README
#####################################################################
# Hybrid (Mamba/GDN) radix cache inserts each prefill chunk's KV pages into the radix
# tree mid-prefill. If the request is then retracted or aborted, cache_finished_req
# frees those pages while the tree still references them. The next request sharing the
# prefix reads another request's pages and decodes an impossible token forever -- the
# "!!!!" loop (token id 0 / 248319), sgl-project/sglang#38319.
#
# Fix (PR #38355): skip the insert for chunked prefill and defer it to
# cache_finished_req. Gated by SGLANG_DISABLE_CHUNKED_RADIX_INSERT (default 1 = fix
# on, 0 = stock behaviour) so it can be A/B'd without rebuilding anything.
#
# All edits are anchored and idempotent: if any anchor does not match EXACTLY once the
# mod refuses to write and exits non-zero, rather than leaving a half-patched tree.
#
# Verify the anchors before trusting a new base image:
#   python3 -c "import sglang, pathlib; \
#     p=pathlib.Path(sglang.__file__).parent/'srt/mem_cache/mamba_radix_cache.py'; \
#     print(p.read_text().count('req.prefix_indices = kv_indices.to(dtype=torch.int64, copy=True)'))"
#####################################################################

#####################################################################
# Metadata
#####################################################################
MOD_NAME="fix-sglang-radix-chunked-insert"
MOD_DESCRIPTION="Defer chunked-prefill radix inserts to request completion (sglang#38319)"
MOD_MAINTAINER="Little Cedar Group <sparkrun@littlecedar.net>"

#####################################################################
# Behaviour
#####################################################################
# Default ON. Set to 0 in the container environment to restore stock behaviour.
export SGLANG_DISABLE_CHUNKED_RADIX_INSERT="${SGLANG_DISABLE_CHUNKED_RADIX_INSERT:-1}"

python3 - <<'PY'
import importlib.util, pathlib, sys

root = pathlib.Path(importlib.util.find_spec("sglang").origin).parent / "srt/mem_cache"

edits = {
    "cache_init_params.py": [(
        "    chunked_prefill_size: Optional[int] = None\n",
        "    chunked_prefill_size: Optional[int] = None\n\n"
        "    # [radix-chunked-insert-fix] skip the radix insert during chunked prefill (sglang#38319)\n"
        "    disable_chunked_radix_insert: bool = False\n")],
    "kv_cache_builder.py": [(
        "    params = CacheInitParams(\n        disable=disable_radix_cache,\n",
        "    # [radix-chunked-insert-fix] sglang#38319: never let the radix tree reference pages of a\n"
        "    # request that can still be retracted. Default on; SGLANG_DISABLE_CHUNKED_RADIX_INSERT=0 restores stock.\n"
        "    import os as _os\n"
        "    _disable_chunked_radix_insert = _os.environ.get(\"SGLANG_DISABLE_CHUNKED_RADIX_INSERT\", \"1\") == \"1\"\n"
        "    if _disable_chunked_radix_insert:\n"
        "        logger.info(\"radix-chunked-insert-fix: chunked-prefill radix insert deferred to request completion (sglang#38319)\")\n"
        "    params = CacheInitParams(\n        disable=disable_radix_cache,\n"
        "        disable_chunked_radix_insert=_disable_chunked_radix_insert,\n")],
    "mamba_radix_cache.py": [(
        "        self.enable_mamba_extra_buffer_lazy = params.enable_mamba_extra_buffer_lazy\n",
        "        self.enable_mamba_extra_buffer_lazy = params.enable_mamba_extra_buffer_lazy\n"
        "        self.disable_chunked_radix_insert = getattr(params, \"disable_chunked_radix_insert\", False)  # [radix-chunked-insert-fix]\n"),
        ("            req.prefix_indices = kv_indices.to(dtype=torch.int64, copy=True)\n            return\n\n        token_ids = req.get_fill_ids()\n",
         "            req.prefix_indices = kv_indices.to(dtype=torch.int64, copy=True)\n            return\n\n"
         "        # [radix-chunked-insert-fix] chunked prefill: only track prefix_indices, insert at completion\n"
         "        if self.disable_chunked_radix_insert and chunked:\n"
         "            return _skip_cache_unfinished_req(req)\n\n"
         "        token_ids = req.get_fill_ids()\n")],
}

changed = []
for name, reps in edits.items():
    p = root / name
    if not p.exists():
        print(f"radix-chunked-insert-fix: {name} NOT FOUND under {root}; wrong sglang layout?")
        sys.exit(1)
    s = p.read_text()
    if "[radix-chunked-insert-fix]" in s:
        print(f"radix-chunked-insert-fix: {name} already applied")
        continue
    # Validate EVERY anchor before writing ANY file, so we never leave a
    # half-patched sglang tree behind on anchor failure.
    for old, _new in reps:
        n = s.count(old)
        if n != 1:
            print(f"radix-chunked-insert-fix: {name}: anchor matched {n} times, expected exactly 1; "
                  f"refusing to patch (base image has diverged?)")
            sys.exit(1)
    for old, new in reps:
        s = s.replace(old, new)
    changed.append((p, s))

for p, s in changed:
    p.write_text(s)
    print(f"radix-chunked-insert-fix: patched {p.name}")

if not changed:
    print("radix-chunked-insert-fix: nothing to do")
PY

#####################################################################
# Smoke test: the patched modules must still import. Cheaper to fail here than
# nine minutes into a weight load with a SyntaxError.
#####################################################################
python3 - <<'PY'
import sys
try:
    import importlib
    import sglang.srt.mem_cache.mamba_radix_cache as m
    importlib.reload(m)
    import sglang.srt.mem_cache.cache_init_params as c
    importlib.reload(c)
except Exception as e:
    print(f"radix-chunked-insert-fix: POST-PATCH IMPORT FAILED: {type(e).__name__}: {e}")
    sys.exit(1)
print("radix-chunked-insert-fix: post-patch import OK")
PY

echo "radix-chunked-insert-fix: SGLANG_DISABLE_CHUNKED_RADIX_INSERT=${SGLANG_DISABLE_CHUNKED_RADIX_INSERT}"
