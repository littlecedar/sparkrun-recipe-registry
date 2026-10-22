"""Guards for tools/refresh-sweep.py — the pin-drift survey CI gates on.

Run:
    uv run python -B -m unittest tests.test_refresh_sweep

Stdlib-only, no network: every registry call is served by a fixture, and a URL
without a fixture is an error, so a test can never quietly reach the internet.

Why this file exists.  The tool's whole value is that a *clean* report means
"nothing fell behind", so the failure that matters is not a wrong number on a
drifting arm — it is a pin the tool could not read being counted as current.
The negative controls below pin exactly that:

* `revision:` is not a model pin, so a recipe carrying only `revision:` must
  come out **unpinned**, never "pinned" (`test_stray_revision_is_not_a_pin`);
* a missing tag at the registry is `container-unresolvable`, never
  `container-current` (`test_missing_tag_is_unresolvable`);
* a tree with no parseable recipe raises instead of reporting an empty sweep
  (`test_empty_selection_raises`, `test_unparseable_recipe_raises`);
* `--apply` refuses a dirty worktree, and on a clean one it touches the
  `container:` line and nothing else — the `model_revision:` bytes are compared
  before and after (`test_apply_leaves_model_pins_alone`);
* the llama.cpp feature map flips when the fetched file text lacks `graph_mtp`,
  which is what "can a stock build replace the fork image?" depends on
  (`test_feature_map_flips_without_graph_mtp`).

Nothing here re-implements the tool.  The fixtures are the measurement; the
test asks the tool to agree with them.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TOOL = REPO_ROOT / "tools" / "refresh-sweep.py"


def _load():
    spec = importlib.util.spec_from_file_location("refresh_sweep", TOOL)
    module = importlib.util.module_from_spec(spec)
    sys.modules["refresh_sweep"] = module  # dash-named tool convention
    spec.loader.exec_module(module)
    return module


sweep_tool = _load()

SHA = "a" * 40
PIN = "b" * 40
NEW_DIGEST = "sha256:" + "c" * 64
OLD_DIGEST = "sha256:" + "d" * 64


class FakeFetch:
    """Ordered `(url substring, response)` rules; an unmatched URL is a failure."""

    def __init__(self, rules):
        self.rules = list(rules)
        self.calls = []

    def __call__(self, url, headers, timeout):
        self.calls.append(url)
        for needle, value in self.rules:
            if needle in url:
                if isinstance(value, Exception):
                    raise value
                if callable(value):
                    return value(url, headers)
                return value
        raise sweep_tool.FetchError(url, "no fixture for this URL", 599)


def UPSTREAM_COMMIT(sha):
    return {"sha": sha, "commit": {"committer": {"date": "2026-10-22T00:00:00Z"}}}


def github_base(upstream_sha="e" * 40, mellum="// MTP: graph_mtp\n", kolibri=True,
                decision2=True, cuda="# CUDA\n121a-real\n"):
    return [
        ("api.github.com/repos/ggml-org/llama.cpp/commits?sha=master",
         (200, {}, json.dumps([UPSTREAM_COMMIT(upstream_sha)]))),
        ("api.github.com/repos/ggml-org/llama.cpp/releases/latest",
         (200, {}, json.dumps({"tag_name": "v0.7.0"}))),
        (f"raw.githubusercontent.com/ggml-org/llama.cpp/{upstream_sha}/src/models/mellum.cpp",
         (200, {}, mellum)),
        (f"raw.githubusercontent.com/ggml-org/llama.cpp/{upstream_sha}/src/models/kolibri1.cpp",
         (200, {}, "// kolibri1\n") if kolibri
         else sweep_tool.FetchError("x", "HTTP 404", 404)),
        (f"raw.githubusercontent.com/ggml-org/llama.cpp/{upstream_sha}/src/models/vllm-decision2.cpp",
         (200, {}, "// vllm-decision2\n") if decision2
         else sweep_tool.FetchError("x", "HTTP 404", 404)),
        (f"raw.githubusercontent.com/ggml-org/llama.cpp/{upstream_sha}/gemm",
         (200, {}, cuda)),
        (f"raw.githubusercontent.com/ggml-org/llama.cpp/{upstream_sha}/ggml/src/ggml-cuda/CMakeLists.txt",
         (200, {}, cuda)),
    ]


def hub_rules(namespace, name, tag, tag_digest, newest="newest-tag"):
    return [
        (f"hub.docker.com/v2/repositories/{namespace}/{name}/tags/{tag}",
         (200, {}, json.dumps({"name": tag, "digest": tag_digest,
                               "last_updated": "2026-10-21T00:00:00Z"}))),
        (f"hub.docker.com/v2/repositories/{namespace}/{name}/tags?",
         (200, {}, json.dumps({"results": [
             {"name": newest, "digest": NEW_DIGEST, "last_updated": "2026-10-21T00:00:00Z"}]}))),
    ]


def hf_rules(repo, head, diff=""):
    return [
        (f"huggingface.co/api/models/{repo}?blobs=false",
         (200, {}, json.dumps({"sha": head, "lastModified": "2026-10-20T00:00:00Z"}))),
        (f"huggingface.co/api/models/{repo}/compare/",
         (200, {}, diff)),
    ]


def all_rules(extra, upstream_sha="e" * 40, **kwargs):
    return github_base(upstream_sha=upstream_sha, **kwargs) + extra


def write_tree(root: Path, files: dict):
    for rel, text in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)


def git_repo(root: Path, files: dict):
    write_tree(root, files)
    env = ["-c", "user.email=guard@example.invalid", "-c", "user.name=guard"]
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    subprocess.run(["git", *env, "add", "-A"], cwd=root, check=True)
    subprocess.run(["git", *env, "commit", "-qm", "fixture"], cwd=root, check=True)


def run_quiet(argv, **kwargs):
    """`run()` with its summary table swallowed, so a failure is readable."""
    import contextlib
    import io

    with contextlib.redirect_stdout(io.StringIO()):
        return sweep_tool.run(argv, **kwargs)


RECIPE = ("recipe_version: \"2\"\n"
          "model: Org/Model:Q4_K_M\n"
          "model_revision: {pin}\n"
          "container: {container}\n")


class Parsing(unittest.TestCase):
    def test_pin_keys_are_read_as_text(self):
        recipe = sweep_tool.parse_recipe(RECIPE.format(pin=PIN, container="ns/img:t"), "r.yaml")
        self.assertEqual(recipe["model"], "Org/Model:Q4_K_M")
        self.assertEqual(recipe["model_revision"], PIN)
        self.assertEqual(sweep_tool.model_repo_id(recipe["model"]), "Org/Model")

    def test_stray_revision_is_not_a_pin(self):
        # The whole point: `revision:` is not sparkrun's key, so this recipe is
        # UNPINNED.  A parse that accepted it would report a moving arm as pinned.
        recipe = sweep_tool.parse_recipe(
            "model: Org/Model\nrevision: " + PIN + "\n", "r.yaml")
        self.assertEqual(recipe["model_revision"], "")
        self.assertEqual(recipe["stray_revision"], PIN)
        row = sweep_tool.classify_model("Org/Model", recipe["model_revision"],
                                        "recipe", "r.yaml", "model", None)
        self.assertEqual(row["class"], sweep_tool.MODEL_UNPINNED)

    def test_indented_keys_are_not_top_level(self):
        recipe = sweep_tool.parse_recipe(
            "model: Org/Model\nruntime_config:\n  model_revision: " + PIN + "\n", "r.yaml")
        self.assertEqual(recipe["model_revision"], "")

    def test_trailing_comment_and_quotes_strip(self):
        recipe = sweep_tool.parse_recipe(
            "model: 'Org/Model'\nmodel_revision: " + PIN + "  # reviewed\n", "r.yaml")
        self.assertEqual(recipe["model"], "Org/Model")
        self.assertEqual(recipe["model_revision"], PIN)

    def test_container_ref_parts(self):
        info = sweep_tool.parse_container_ref("lmsysorg/sglang:dev-cu13@sha256:" + "0" * 64)
        self.assertEqual((info["host"], info["repo"], info["tag"]),
                         ("docker.io", "lmsysorg/sglang", "dev-cu13"))
        self.assertEqual(info["digest"], "sha256:" + "0" * 64)
        official = sweep_tool.parse_container_ref("python:3.12-slim@sha256:" + "0" * 64)
        self.assertEqual(official["repo"], "library/python")
        ghcr = sweep_tool.parse_container_ref("ghcr.io/ns/deep/name@sha256:" + "0" * 64)
        self.assertEqual((ghcr["host"], ghcr["repo"]), ("ghcr.io", "ns/deep/name"))
        self.assertEqual(ghcr["tag"], "")

    def test_template_ref_is_unresolvable(self):
        info = sweep_tool.parse_container_ref("{container_ref}")
        self.assertTrue(info["error"])

    def test_dockerfile_args_pair(self):
        parsed = sweep_tool.parse_dockerfile(
            "FROM --platform=linux/arm64 nvidia/cuda:13.0.1-devel@sha256:" + "0" * 64 + " AS build\n"
            "ARG LLAMA_REPO=https://github.com/brywil/llama.cpp.git\n"
            "ARG LLAMA_REF=68fa28b56\n")
        self.assertEqual(parsed["froms"], ["nvidia/cuda:13.0.1-devel@sha256:" + "0" * 64])
        self.assertEqual(sweep_tool.github_repo(parsed["args"]["LLAMA_REPO"]),
                         "brywil/llama.cpp")
        self.assertEqual(parsed["args"]["LLAMA_REF"], "68fa28b56")


class FailClosed(unittest.TestCase):
    def test_unparseable_recipe_raises(self):
        with self.assertRaises(sweep_tool.SweepError):
            sweep_tool.parse_recipe("description: nothing pinnable here\n", "r.yaml")

    def test_empty_selection_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "recipes" / "lane").mkdir(parents=True)
            fetcher = sweep_tool.Fetcher(fetch=FakeFetch(github_base()))
            with self.assertRaises(sweep_tool.SweepError):
                sweep_tool.sweep(Path(tmp), fetcher, lane="lane")

    def test_missing_recipe_path_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_tree(Path(tmp), {"recipes/lane/a.yaml": RECIPE.format(
                pin=PIN, container="ns/img:t@sha256:" + "0" * 64)})
            with self.assertRaises(sweep_tool.SweepError):
                run_quiet(["--recipe", "recipes/lane/nope.yaml"], root=tmp)

    def test_main_exits_2_on_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            code = sweep_tool.main(["--recipe", str(Path(tmp) / "nope.yaml"),
                                    "--timeout", "1"])
            self.assertEqual(code, 2)

    def test_sweep_never_returns_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_tree(Path(tmp), {
                "recipes/lane/a.yaml": "model: Org/Model\ncontainer: ns/img:t@sha256:" + "0" * 64 + "\n",
            })
            fetcher = sweep_tool.Fetcher(fetch=FakeFetch(all_rules(
                hub_rules("ns", "img", "t", "sha256:" + "0" * 64)
                + hf_rules("Org/Model", PIN))))
            report = sweep_tool.sweep(Path(tmp), fetcher)
            self.assertTrue(report["rows"], "a sweep with pins must never come back empty")
            classes = {row["class"] for row in report["rows"] if row["scope"] == "recipe"}
            self.assertIn(sweep_tool.MODEL_UNPINNED, classes)


class Models(unittest.TestCase):
    def _classify(self, pin, head, diff):
        rules = hf_rules("Org/Model", head, diff)
        fetcher = sweep_tool.Fetcher(fetch=FakeFetch(rules))
        return sweep_tool.classify_model("Org/Model", pin, "recipe", "r.yaml", "model", fetcher)

    def test_pin_at_head_is_current(self):
        row = self._classify(PIN, PIN, "")
        self.assertEqual(row["class"], sweep_tool.MODEL_CURRENT)

    def test_weight_change_is_stale_weights(self):
        diff = ("diff --git a/model-00001-of-00002.safetensors b/model-00001-of-00002.safetensors\n"
                "diff --git a/README.md b/README.md\n")
        self.assertEqual(self._classify(PIN, SHA, diff)["class"],
                         sweep_tool.MODEL_STALE_WEIGHTS)

    def test_docs_only_change_is_stale_docs(self):
        diff = ("diff --git a/chat_template.jinja b/chat_template.jinja\n"
                "diff --git a/README.md b/README.md\n")
        row = self._classify(PIN, SHA, diff)
        self.assertEqual(row["class"], sweep_tool.MODEL_STALE_DOCS)
        self.assertEqual(row["observed"], SHA)

    def test_empty_diff_with_moved_head_is_unresolvable(self):
        # Fail closed: pin != head but no diff is a contradiction, not "clean".
        self.assertEqual(self._classify(PIN, SHA, "")["class"],
                         sweep_tool.MODEL_UNRESOLVABLE)

    def test_network_failure_is_unresolvable(self):
        fetcher = sweep_tool.Fetcher(fetch=FakeFetch(
            [("huggingface.co/api/models/Org/Model", sweep_tool.FetchError("x", "HTTP 401", 401))]))
        row = sweep_tool.classify_model("Org/Model", PIN, "recipe", "r.yaml", "model", fetcher)
        self.assertEqual(row["class"], sweep_tool.MODEL_UNRESOLVABLE)

    def test_repo_id_keeps_owner_case(self):
        seen = []

        def record(url, headers):
            seen.append(url)
            return (200, {}, json.dumps({"sha": PIN}))

        fetcher = sweep_tool.Fetcher(fetch=FakeFetch(
            [("huggingface.co/api/models/", record)]))
        row = sweep_tool.classify_model("inclusionAI/Ling-3.0-flash-int4", PIN,
                                        "recipe", "r.yaml", "model", fetcher)
        self.assertEqual(row["class"], sweep_tool.MODEL_CURRENT)
        self.assertIn("inclusionAI/Ling-3.0-flash-int4", seen[0])


class Containers(unittest.TestCase):
    def _classify(self, ref, rules):
        fetcher = sweep_tool.Fetcher(fetch=FakeFetch(rules))
        return sweep_tool.classify_container(ref, fetcher, "recipe", "r.yaml")

    def test_same_digest_is_current(self):
        ref = "ns/img:t@sha256:" + "0" * 64
        row = self._classify(ref, hub_rules("ns", "img", "t", "sha256:" + "0" * 64))
        self.assertEqual(row["class"], sweep_tool.CONTAINER_CURRENT)
        self.assertFalse(row.get("appliable"))
        # the newest tag is reported for the operator, not applied
        self.assertEqual(row["newest_tag"], "newest-tag")

    def test_moved_tag_is_newer_release_and_appliable(self):
        ref = "ns/img:t@sha256:" + "0" * 64
        row = self._classify(ref, hub_rules("ns", "img", "t", NEW_DIGEST))
        self.assertEqual(row["class"], sweep_tool.CONTAINER_NEWER_RELEASE)
        self.assertTrue(row["appliable"])
        self.assertEqual(row["new_digest"], NEW_DIGEST)
        self.assertEqual(row["new_tag"], "t")

    def test_missing_tag_is_unresolvable(self):
        # Negative control: no matching tag must NOT read as current.
        ref = "ns/img:gone@sha256:" + "0" * 64
        rules = [("hub.docker.com/v2/repositories/ns/img/tags/gone",
                  sweep_tool.FetchError("x", "HTTP 404", 404)),
                 ("hub.docker.com/v2/repositories/ns/img/tags?", (200, {}, json.dumps(
                     {"results": [{"name": "other", "digest": NEW_DIGEST,
                                   "last_updated": "2026-10-21T00:00:00Z"}]})))]
        self.assertEqual(self._classify(ref, rules)["class"],
                         sweep_tool.CONTAINER_UNRESOLVABLE)

    def test_tag_without_digest_is_floating(self):
        row = self._classify("ns/img:t", [])
        self.assertEqual(row["class"], sweep_tool.CONTAINER_FLOATING)

    def test_ghcr_moved_tag(self):
        ref = "ghcr.io/ns/name:t@sha256:" + "0" * 64
        rules = [
            ("ghcr.io/token?scope=repository:ns/name:pull", (200, {}, json.dumps({"token": "t"}))),
            ("ghcr.io/v2/ns/name/manifests/t",
             (200, {"docker-content-digest": NEW_DIGEST}, "{}")),
        ]
        row = self._classify(ref, rules)
        self.assertEqual(row["class"], sweep_tool.CONTAINER_NEWER_RELEASE)
        self.assertEqual(row["new_digest"], NEW_DIGEST)

    def test_unknown_registry_is_unresolvable(self):
        row = self._classify("quay.io/ns/name:t@sha256:" + "0" * 64, [])
        self.assertEqual(row["class"], sweep_tool.CONTAINER_UNRESOLVABLE)


class LlamaCpp(unittest.TestCase):
    DOCKERFILE = ("FROM nvidia/cuda:13.0.1-devel@sha256:" + "1" * 64 + " AS build\n"
                  "ARG LLAMA_REPO=https://github.com/brywil/llama.cpp.git\n"
                  "ARG LLAMA_REF=68fa28b564f09a2bfa4ee590da35b6f55defae59\n")

    def _collect(self, **features):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_tree(root, {
                "recipes/explore/Dockerfile.x": self.DOCKERFILE,
                "recipes/explore/arm.yaml": RECIPE.format(
                    pin=PIN, container="ns/llama-cpp:t@sha256:" + "0" * 64),
            })
            rules = all_rules([
                ("hub.docker.com/v2/repositories/nvidia/cuda/tags/13.0.1-devel",
                 (200, {}, json.dumps({"digest": "sha256:" + "1" * 64}))),
                ("hub.docker.com/v2/repositories/nvidia/cuda/tags?",
                 (200, {}, json.dumps({"results": [{"name": "13.0.1-devel",
                                                    "digest": "sha256:" + "1" * 64}]}))),
                ("hub.docker.com/v2/repositories/ns/llama-cpp/tags?",
                 (200, {}, json.dumps({"results": [
                     {"name": "b10549", "digest": NEW_DIGEST,
                      "last_updated": "2026-08-21T00:00:00Z"}]}))),
                ("api.github.com/repos/brywil/llama.cpp/commits/68fa28b",
                 (200, {}, json.dumps([{"name": "kolibri1"}]))),
                ("api.github.com/repos/brywil/llama.cpp/compare/68fa28b",
                 (200, {}, json.dumps({"behind_by": 0, "ahead_by": 0}))),
                ("api.github.com/repos/brywil/llama.cpp/compare/ggml-org:master",
                 (200, {}, json.dumps({"behind_by": 929, "ahead_by": 2}))),
                ("hub.docker.com/v2/repositories/Org/Model", sweep_tool.FetchError("x", "skip", 599)),
            ] + hf_rules("Org/Model", PIN), **features)
            fetcher = sweep_tool.Fetcher(fetch=FakeFetch(rules))
            return sweep_tool.collect_llama_cpp(
                root, sweep_tool.tracked_paths(root), ["recipes/explore/arm.yaml"], fetcher)

    def test_feature_map_flips_without_graph_mtp(self):
        # Negative control: the same fixture minus the needle must flip to False.
        with_needle = self._collect()["upstream_supports"]
        without = self._collect(mellum="# Mellum, no MTP support\n")["upstream_supports"]
        self.assertTrue(with_needle["graph_mtp"])
        self.assertFalse(without["graph_mtp"])
        self.assertTrue(without["kolibri1"])
        self.assertTrue(without["121a-real"])

    def test_missing_model_file_is_false_not_unknown(self):
        supports = self._collect(kolibri=False, decision2=False)["upstream_supports"]
        self.assertFalse(supports["kolibri1"])
        self.assertFalse(supports["vllm-decision2"])

    def test_refs_carry_upstream_gap_and_own_branch(self):
        section = self._collect()
        ref = section["refs"][0]
        self.assertEqual(ref["branch"], "kolibri1")
        self.assertEqual(ref["behind_by"], 929)       # vs upstream master
        self.assertEqual(ref["branch_behind_by"], 0)  # vs its own branch
        self.assertEqual(section["images"][0]["publisher_latest_tag"], "b10549")


class Cache(unittest.TestCase):
    def test_cache_hit_skips_fetch_and_records_time(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache = Path(tmp) / "cache.json"
            rule = ("https://example.invalid/x", (200, {}, "body"))
            first = sweep_tool.Fetcher(cache_path=cache, fetch=FakeFetch([rule]))
            self.assertEqual(first.get("https://example.invalid/x")[2], "body")
            first.save()
            stored = json.loads(cache.read_text())["https://example.invalid/x"]
            self.assertIn("cached_at", stored)
            second_fetch = FakeFetch([rule])
            second = sweep_tool.Fetcher(cache_path=cache, fetch=second_fetch)
            self.assertEqual(second.get("https://example.invalid/x")[2], "body")
            self.assertEqual(second_fetch.calls, [], "a fresh entry must not refetch")

    def test_stale_cache_is_refetched(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache = Path(tmp) / "cache.json"
            cache.write_text(json.dumps({"https://example.invalid/x": {
                "fetched_at": 0, "cached_at": "1970-01-01T00:00:00Z", "status": 200,
                "headers": {}, "body": "stale"}}))
            fetch = FakeFetch([("https://example.invalid/x", (200, {}, "fresh"))])
            fetcher = sweep_tool.Fetcher(cache_path=cache, fetch=fetch)
            self.assertEqual(fetcher.get("https://example.invalid/x")[2], "fresh")
            self.assertEqual(len(fetch.calls), 1)

    def test_cache_miss_is_fetched(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache = Path(tmp) / "cache.json"
            cache.write_text(json.dumps({}))
            fetch = FakeFetch([("https://example.invalid/y", (200, {}, "y"))])
            fetcher = sweep_tool.Fetcher(cache_path=cache, fetch=fetch)
            self.assertEqual(fetcher.get("https://example.invalid/y")[2], "y")


class Apply(unittest.TestCase):
    ARM = ("recipe_version: \"2\"\n"
           "model: Org/Model\n"
           "model_revision: " + PIN + "\n"
           "container: ns/img:t@sha256:" + "0" * 64 + "\n")

    def _rules(self):
        return all_rules(
            hub_rules("ns", "img", "t", NEW_DIGEST)
            + hf_rules("Org/Model", SHA,
                       "diff --git a/model.safetensors b/model.safetensors\n"))

    def test_refuses_dirty_worktree(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            git_repo(root, {"recipes/lane/a.yaml": self.ARM})
            (root / "recipes/lane/a.yaml").write_text(self.ARM + "# local edit\n")
            with self.assertRaises(sweep_tool.SweepError) as caught:
                run_quiet(["--apply"], fetch=FakeFetch(self._rules()), root=tmp)
            self.assertIn("dirty worktree", str(caught.exception))

    def test_apply_leaves_model_pins_alone(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            arm = "recipes/lane/a.yaml"
            git_repo(root, {arm: self.ARM})
            code, report = run_quiet(["--apply"], fetch=FakeFetch(self._rules()), root=tmp)
            self.assertEqual(code, 0, "default exit is 0; only --exit-code gates drift")
            text = (root / arm).read_text()
            self.assertIn("container: ns/img:t@" + NEW_DIGEST, text)
            self.assertIn("model_revision: " + PIN, text)  # untouched: boot-gated by policy
            self.assertEqual(len(report["applied"]), 1)

    def test_apply_skips_floating_container(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            arm = "recipes/lane/b.yaml"
            floating = self.ARM.replace("ns/img:t@sha256:" + "0" * 64, "ns/img:t")
            git_repo(root, {arm: floating})
            rules = all_rules(hf_rules("Org/Model", PIN))
            _code, report = run_quiet(["--apply"], fetch=FakeFetch(rules), root=tmp)
            self.assertEqual(report["applied"], [])
            self.assertIn("container: ns/img:t\n", (root / arm).read_text())

    def test_exit_codes_and_only_filter(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            git_repo(root, {"recipes/lane/a.yaml": self.ARM})
            rules = self._rules()
            code, _report = run_quiet(["--exit-code"], fetch=FakeFetch(rules), root=tmp)
            self.assertEqual(code, 1, "drift present must gate as 1")
            code, _report = run_quiet(["--exit-code", "--only", "container-current"],
                                           fetch=FakeFetch(rules), root=tmp)
            self.assertEqual(code, 0, "a filter that selects no drift must gate as 0")
            with self.assertRaises(sweep_tool.SweepError):
                run_quiet(["--only", "model-curent"], fetch=FakeFetch(rules), root=tmp)

    def test_unresolvable_row_gates_as_2(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            git_repo(root, {"recipes/lane/a.yaml": self.ARM})
            rules = all_rules([("huggingface.co/api/models/Org/Model",
                                sweep_tool.FetchError("x", "HTTP 503", 503))])
            code, _report = run_quiet(["--exit-code"], fetch=FakeFetch(rules), root=tmp)
            self.assertEqual(code, 2)


if __name__ == "__main__":
    unittest.main()
