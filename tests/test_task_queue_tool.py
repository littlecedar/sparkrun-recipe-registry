"""Guards for tools/task-queue.py — the owner's task-queueing policy, mechanized.

Run:
    uv run python -B -m unittest discover -s tests

Stdlib-only, no network, no cluster, like every other guard here.

What is pinned (owner policy 2026-10-26, verbatim; the dated decisions live in
`mad-science/TODO.md` §"Retry queue — window 4"; protocol in `mad-science/QUEUE.md`):

* weight arithmetic — simple and transitive: a task's weight is its estimate minus the sum of
  the estimates of everything it transitively blocks (`test_simple_weight`,
  `test_transitive_weight_is_the_chain_total`);
* the owner's own 48 h / 24 h illustration: a 24 h task blocking 24 h of work in a 48 h queue
  weighs 0 and floats to the top (`test_owner_48h_24h_example_floats_to_the_top`);
* a done blocker stops contributing credit, so its dependents' weights rise
  (`test_done_tasks_stop_contributing_credit`);
* the priority override — DeepSeek-V4.1-Flash-1017 (either tag spelling) before GLM-5.3 before
  GLM-5.3-Flash before everything else, weight ascending within a tier
  (`test_tiering_prioritizes_the_owner_models`, `test_weight_orders_within_a_tier`);
* fail-closed validation, each with a negative control: a `blocks` cycle (a 2-cycle is refused,
  `test_two_cycle_is_refused`), a dangling id, a missing estimate, a non-numeric estimate
  (`test_dangling_ref_is_refused`, `test_missing_estimate_is_refused`,
  `test_non_numeric_estimate_is_refused`);
* `done` drops a task from the ordering and releases its blocking credit, so the queue
  re-sorts (`test_done_removes_task_and_releases_blocked_credit`).

Nothing here re-implements the tool: the fixtures are minimal task dicts and the assertions are
the properties.
"""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TOOL = REPO_ROOT / "tools" / "task-queue.py"


def _load():
    spec = importlib.util.spec_from_file_location("task_queue", TOOL)
    module = importlib.util.module_from_spec(spec)
    sys.modules["task_queue"] = module  # dash-named tool convention
    spec.loader.exec_module(module)
    return module


tq = _load()


def task(tid, est, blocks=(), model="", state="queued"):
    return {
        "id": tid, "title": tid, "estimate_h": est, "blocks": list(blocks),
        "blocked_by": [], "state": state, "model": model, "node_cost": "",
        "notes": "", "provenance": "test",
    }


def relink(tasks):
    mirror = tq.derived_blocked_by(tasks)
    for t in tasks:
        t["blocked_by"] = sorted(mirror.get(t["id"], set()))
    return tasks


# The seeded tier list: a tier may be a list of equivalent tags — the registry spells the
# primary model both ways, and both spellings must share tier 0.
def data(tasks, priority_models=(["deepseek-v4.1-flash-1017", "dsv4.1-1017"], "glm-5.3", "glm-5.3-flash")):
    return {"priority_models": [list(t) if isinstance(t, list) else t for t in priority_models],
            "tasks": relink(list(tasks))}


def ids(ordered):
    return [t["id"] for t in ordered]


class WeightArithmetic(unittest.TestCase):
    def test_simple_weight(self):
        a = task("a", 2.0)
        weight, blocked = tq.compute_weight(a, [a])
        self.assertEqual(weight, 2.0)
        self.assertEqual(blocked, {})

    def test_transitive_weight_is_the_chain_total(self):
        # a -> b -> c: a's credit is b + c (24), not just its direct dependent b (12).
        a, b, c = task("a", 24.0, ["b"]), task("b", 12.0, ["c"]), task("c", 12.0)
        tasks = relink([a, b, c])
        weight, blocked = tq.compute_weight(tasks[0], tasks)
        self.assertEqual(weight, 0.0)
        self.assertEqual(blocked, {"b": 12.0, "c": 12.0})

    def test_owner_48h_24h_example_floats_to_the_top(self):
        # The owner's illustration: a 48-hour-deep queue whose 24 h task blocks 24 h of work
        # weighs 0 and takes the top slot despite being the most expensive item. The two
        # blocked tasks are a fan-out (x -> a 12 h, x -> b 12 h) so x alone weighs 0.
        x = task("x", 24.0, ["a", "b"])
        a, b = task("a", 12.0), task("b", 12.0)
        filler1, filler2 = task("f1", 20.0), task("f2", 20.0)
        ordered = tq.ordering(data([filler1, x, a, b, filler2]))
        self.assertEqual(ids(ordered)[0], "x")
        self.assertEqual(ids(ordered)[1:], ["a", "b", "f1", "f2"])
        weight, _ = tq.compute_weight(x, [x, a, b, filler1, filler2])
        self.assertEqual(weight, 0.0)

    def test_done_tasks_stop_contributing_credit(self):
        # A done blocker no longer blocks: its dependents' weights rise and it drops out.
        a, b, c = task("a", 24.0, ["b"]), task("b", 12.0, ["c"]), task("c", 12.0, state="done")
        tasks = relink([a, b, c])
        weight, blocked = tq.compute_weight(tasks[0], tasks)
        self.assertEqual((weight, blocked), (12.0, {"b": 12.0}))


class Tiering(unittest.TestCase):
    def test_tiering_prioritizes_the_owner_models(self):
        tasks = [
            task("other", 0.1, model="whatever"),
            task("glm-flash", 0.1, model="glm-5.3-flash"),
            task("glm", 0.1, model="glm-5.3"),
            task("dsv-alias", 0.1, model="dsv4.1-1017"),
            task("dsv-long", 0.1, model="DeepSeek-V4.1-Flash-1017"),
        ]
        self.assertEqual(ids(tq.ordering(data(tasks))),
                         ["dsv-alias", "dsv-long", "glm", "glm-flash", "other"])

    def test_weight_orders_within_a_tier(self):
        tasks = [
            task("heavy", 10.0, model="glm-5.3"),
            task("light-gater", 1.0, ["heavy", "other-glm"], model="glm-5.3"),
            task("other-glm", 2.0, model="glm-5.3"),
        ]
        self.assertEqual(ids(tq.ordering(data(tasks))), ["light-gater", "other-glm", "heavy"])


class FailClosed(unittest.TestCase):
    def test_two_cycle_is_refused(self):
        tasks = relink([task("p", 1.0, ["q"]), task("q", 1.0, ["p"])])
        with self.assertRaises(tq.QueueError) as ctx:
            tq.validate(data(tasks, priority_models=["x"]))
        self.assertIn("cycle", str(ctx.exception))
        self.assertIn("p -> q -> p", str(ctx.exception))

    def test_dangling_ref_is_refused(self):
        tasks = relink([task("p", 1.0, ["ghost"])])
        with self.assertRaises(tq.QueueError) as ctx:
            tq.validate(data(tasks, priority_models=["x"]))
        self.assertIn("ghost", str(ctx.exception))

    def test_missing_estimate_is_refused(self):
        bad = task("p", 1.0)
        del bad["estimate_h"]
        with self.assertRaises(tq.QueueError) as ctx:
            tq.validate(data([bad], priority_models=["x"]))
        self.assertIn("estimate_h", str(ctx.exception))

    def test_non_numeric_estimate_is_refused(self):
        bad = task("p", "two")
        with self.assertRaises(tq.QueueError) as ctx:
            tq.validate(data([bad], priority_models=["x"]))
        self.assertIn("p", str(ctx.exception))

    def test_cli_exits_non_zero_on_a_cycle(self):
        # Negative control at the CLI layer: the same 2-cycle exits 1 with the message on stderr.
        payload = data([task("p", 1.0, ["q"]), task("q", 1.0, ["p"])], priority_models=["x"])
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "queue.json"
            path.write_text(json.dumps(payload))
            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr):
                rc = tq.main(["--file", str(path), "queue"])
        self.assertEqual(rc, 1)
        self.assertIn("cycle", stderr.getvalue())

    def test_cli_check_and_queue_exit_zero_on_the_seeded_queue(self):
        # The tracked seed itself must validate and order cleanly (no mutation on read).
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            self.assertEqual(tq.main(["--file", str(REPO_ROOT / "mad-science" / "queue.json"), "check"]), 0)
            self.assertEqual(tq.main(["--file", str(REPO_ROOT / "mad-science" / "queue.json"), "queue"]), 0)
        self.assertEqual(stderr.getvalue(), "")


class UpdateRepairsDrift(unittest.TestCase):
    def test_update_relinks_before_validating(self):
        """`check` tells the reader to rerun `update`; that must be able to succeed.

        The mirror is derived from `blocks`, so a register whose `blocked_by` drifted is exactly the
        state `update` exists to repair -- and it used to validate first, so every rerun died on the
        same line. Measured 2026-10-30: three attempts, each printing the same instruction.
        """
        payload = data([task("a", 1.0, ["b"]), task("b", 2.0, [])], priority_models=["x"])
        payload["tasks"][1]["blocked_by"] = []          # a drift the mirror says should be ["a"]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "queue.json"
            path.write_text(json.dumps(payload))
            self.assertNotEqual(tq.main(["--file", str(path), "check"]), 0)
            self.assertEqual(tq.main(["--file", str(path), "update", "--id", "b", "--notes", "x"]), 0)
            self.assertEqual(tq.main(["--file", str(path), "check"]), 0)

    def test_pair_is_a_valid_node_cost(self):
        """A TP=2 arm is a pair; the checklist predated it and forced a caveat in `notes`."""
        self.assertIn("pair", tq.NODE_COSTS)


class QuestionsAndCommitBound(unittest.TestCase):
    """The two schema additions chosen 2026-11-03: a questions register, and a commit-bounded
    archive scan (the count bound netted out when one item was removed as another arrived)."""

    def _repo(self, tmp):
        import subprocess
        root = Path(tmp)
        (root / "q.json").write_text(json.dumps(data([task("a", 1.0)])), encoding="utf-8")
        (root / "TODO.md").write_text("- [ ] **old item**\n", encoding="utf-8")
        env = ["-c", "user.email=g@example.invalid", "-c", "user.name=g"]
        subprocess.run(["git", "init", "-q"], cwd=root, check=True)
        subprocess.run(["git", *env, "add", "-A"], cwd=root, check=True)
        subprocess.run(["git", *env, "commit", "-qm", "freeze"], cwd=root, check=True)
        return root

    def test_orphans_since_bounds_the_scan(self):
        # Only items ADDED after the boundary count: the frozen file's own item is not an orphan.
        with tempfile.TemporaryDirectory() as tmp:
            root = self._repo(tmp)
            todo = root / "TODO.md"
            with open(todo, "a", encoding="utf-8") as fh:
                fh.write("- [ ] **new item**\n")
            argv = ["--file", str(root / "q.json"), "orphans", "--todo", str(todo), "--since", "HEAD"]
            with contextlib.redirect_stdout(io.StringIO()) as out:
                code = tq.main(argv)
            self.assertEqual(code, 1, "a post-cutover item is the defect")
            self.assertIn("new item", out.getvalue())
            self.assertNotIn("old item", out.getvalue())

    def test_question_numbering_only_grows(self):
        payload = data([task("a", 1.0)])
        row = {"id": 5, "summary": "s", "status": "open", "provenance": "p", "asked": "2026-11-03"}
        payload["questions"] = [row, dict(row, id=3)]
        with self.assertRaises(tq.QueueError):
            tq.validate(payload)
        payload["questions"] = [row, dict(row)]
        with self.assertRaises(tq.QueueError):
            tq.validate(payload)

    def test_questions_command_lists_only_open_rows(self):
        payload = data([task("a", 1.0)])
        payload["questions"] = [
            {"id": 1, "summary": "settled thing", "status": "answered 2026-11-02",
             "provenance": "p", "asked": "2026-11-01"},
            {"id": 2, "summary": "open thing", "status": "open", "provenance": "p",
             "asked": "2026-11-03"},
        ]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "queue.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()) as out:
                self.assertEqual(tq.main(["--file", str(path), "questions"]), 0)
            text = out.getvalue()
            self.assertIn("open thing", text)
            self.assertNotIn("settled thing", text, "a settled row leaves the array")


class Done(unittest.TestCase):
    def test_done_removes_task_and_releases_blocked_credit(self):
        # a (4 h) gates b (2 h) and c (2 h): a weighs 0 and floats. Marking c done drops c
        # from the ordering and releases half of a's credit, so a's weight rises to 2.
        a = task("a", 4.0, ["b", "c"])
        b, c = task("b", 2.0), task("c", 2.0)
        tasks = relink([a, b, c])
        self.assertEqual(ids(tq.ordering(data(tasks))), ["a", "b", "c"])
        c_state = dict(c, state="done")
        ordered = tq.ordering(data([a, b, c_state]))
        self.assertEqual(ids(ordered), ["a", "b"])
        weight, blocked = tq.compute_weight(a, [a, b, c_state])
        self.assertEqual((weight, blocked), (2.0, {"b": 2.0}))


if __name__ == "__main__":
    unittest.main()

class AtomicSave(unittest.TestCase):
    """A torn write here does not look like corruption -- JSON stays valid while rows vanish."""

    def test_a_failed_replace_leaves_the_register_untouched(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "queue.json"
            path.write_text(json.dumps({"priority_models": [], "tasks": [task("a", 1.0)]}), encoding="utf-8")
            before = path.read_bytes()
            orig = tq.os.replace
            tq.os.replace = lambda *a, **k: (_ for _ in ()).throw(OSError("boom"))
            try:
                with self.assertRaises(OSError):
                    tq._save(path, {"priority_models": []}, [task("a", 1.0), task("b", 2.0)])
            finally:
                tq.os.replace = orig
            self.assertEqual(path.read_bytes(), before, "the register must be unchanged")
            self.assertEqual([p.name for p in Path(tmp).iterdir()], ["queue.json"], "no temp file left")

    def test_the_saved_register_keeps_its_mode(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "queue.json"
            path.write_text("{}", encoding="utf-8")
            path.chmod(0o640)
            tq._save(path, {"priority_models": []}, [task("a", 1.0)])
            self.assertEqual(path.stat().st_mode & 0o777, 0o640)


class BoardAndArchive(unittest.TestCase):
    """`render --board` and `orphans`: the queue is the register, TODO.md is the archive."""

    def test_board_emits_the_status_columns(self):
        payload = data([task("b", 1.0), task("a", 2.0, ["b"])])
        rows = tq.board_rows(payload)
        self.assertEqual(rows[0], "| job | node cost | holds | state |")
        self.assertTrue(all(r.count("|") == 5 for r in rows), "four columns, as the board has")
        body = "\n".join(rows[2:])
        self.assertIn("`a`", body)
        self.assertIn("`b`", body)
        self.assertIn("queued", body)

    def test_board_carries_notes_and_evidence(self):
        t = task("a", 1.0)
        t["notes"] = "why this arm exists"
        t["evidence"] = "~/benchmarks/lane-20261103/REPORT.md"
        body = "\n".join(tq.board_rows(data([t])))
        self.assertIn("why this arm exists", body)
        self.assertIn("evidence: `~/benchmarks/lane-20261103/REPORT.md`", body)

    def test_board_survives_multiline_and_piped_notes(self):
        # A note is prose: a newline here ends the markdown table, a raw pipe splits the cell.
        t = task("a", 1.0)
        t["notes"] = "first line\n\nFraming: `p50` vs NVMe | staging withdrawn"
        rows = tq.board_rows(data([t]))
        self.assertEqual(len(rows), 3, "one row per task, never a wrapped line")
        self.assertTrue(all(len(re.split(r"(?<!\\)\|", r)) == 6 for r in rows), "four cells per row")
        self.assertIn(r"vs NVMe \| staging", rows[2])
        self.assertIn("first line Framing:", rows[2])

    def test_evidence_must_be_a_string(self):
        # Negative control: a non-string evidence is a data defect, never silently ignored.
        payload = data([task("a", 1.0)])
        payload["tasks"][0]["evidence"] = ["a", "list"]
        with self.assertRaises(tq.QueueError):
            tq.validate(payload)

    def test_orphans_flags_an_unmarked_item(self):
        text = "## lane\n- [ ] **Fix the thing** — detail\n"
        orphans, dead = tq.todo_orphans(text, [task("a", 1.0)])
        self.assertEqual([t for _line, t in orphans], ["Fix the thing"])
        self.assertEqual(dead, [])

    def test_orphans_accepts_a_live_marker_on_the_next_line(self):
        text = "- [ ] **Fix the thing** — detail\n  <!-- queue: a -->\n"
        orphans, dead = tq.todo_orphans(text, [task("a", 1.0)])
        self.assertEqual((orphans, dead), ([], []))

    def test_orphans_flags_a_dead_marker(self):
        # A renamed task must not silently orphan the text its old marker covered.
        text = "- [ ] **Fix the thing** <!-- queue: renamed-away -->\n"
        orphans, dead = tq.todo_orphans(text, [task("a", 1.0)])
        self.assertEqual(orphans, [])
        self.assertEqual([ref for _line, _t, ref in dead], ["renamed-away"])

    def test_orphans_allow_permits_grandfathered_but_not_growth(self):
        # The bound is the cutover, not an amnesty: the archive's pre-freeze items are
        # tolerated, one new unmarked item is not.
        with tempfile.TemporaryDirectory() as tmp:
            queue = Path(tmp) / "queue.json"
            queue.write_text(json.dumps(data([task("a", 1.0)])), encoding="utf-8")
            todo = Path(tmp) / "TODO.md"
            todo.write_text("- [ ] **one**\n- [ ] **two**\n", encoding="utf-8")
            argv = ["--file", str(queue), "orphans", "--todo", str(todo), "--allow", "2"]
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(tq.main(argv), 0, "the frozen count is tolerated")
                with open(todo, "a", encoding="utf-8") as fh:
                    fh.write("- [ ] **three**\n")
                self.assertEqual(tq.main(argv), 1, "growth past the bound is the defect")

    def test_archive_does_not_grow(self):
        """TODO.md is frozen: its open-item count may not move without a queue row.

        52 is the archive's open-item count at the 2026-11-03 freeze, when the register
        became `mad-science/queue.json` and the board began rendering from it. The count
        is pinned rather than matched item-by-item because the archive's text is evidence,
        not schedule — importing it into JSON would be a second restatement of prose. A
        genuinely new item goes to the queue; if one legitimately lands in the archive,
        import it and bump this number in the same commit.
        """
        todo = REPO_ROOT / "mad-science" / "TODO.md"
        payload = json.loads((REPO_ROOT / "mad-science" / "queue.json").read_text(encoding="utf-8"))
        orphans, dead = tq.todo_orphans(todo.read_text(encoding="utf-8"), tq.validate(payload))
        self.assertEqual(dead, [], "a marker naming an unknown task")
        self.assertEqual(len(orphans), 52,
                         "the archive grew (or shrank without a marker): " +
                         "; ".join(t for _line, t in orphans[:5]))


class MarkdownLint(unittest.TestCase):
    """`lint`: a table that GFM will not render is refused before it is published.

    The defect this exists for shipped twice (2026-10-22 and 2026-11-03, `6f19662` and the
    landed table below): a header row followed straight by data rows, with no
    `|---|---|---|` delimiter, which GFM does not read as a table at all — every row becomes
    one paragraph of literal pipes. `render --board` now refuses its own output, and the
    board itself is linted here because the tick that writes the rest of the file runs
    outside this repo.
    """

    # The board's landed table as it was published on 2026-11-03: header, then a data row.
    BROKEN = (
        "## Landed session\n\n"
        "| time ET | commit | one clause |\n"
        "| 16:32 ET | `15f5bcd` | a clause |\n"
        "| 16:34 ET | `c4e5d53` | another clause |\n"
    )

    def test_missing_delimiter_is_caught(self):
        # Negative control: the pre-fix block above must be flagged, or the guard proves nothing.
        rules = [r for _line, r, _d in tq.lint_markdown(self.BROKEN)]
        self.assertEqual(rules, ["table-missing-delimiter"])

    def test_delimiter_makes_the_same_block_render(self):
        fixed = self.BROKEN.replace("| one clause |\n", "| one clause |\n|---|---|---|\n")
        self.assertEqual(tq.lint_markdown(fixed), [])

    def test_ragged_row_is_caught(self):
        text = "| a | b | c |\n|---|---|---|\n| 1 | 2 |\n"
        self.assertEqual([r for _l, r, _d in tq.lint_markdown(text)], ["table-ragged"])

    def test_pipe_inside_a_code_span_is_caught(self):
        # GFM splits cells before parsing inline markup, so a piped shell command needs `\\|`.
        text = "| a | b |\n|---|---|\n| `find . -name x | wc -l` | y |\n"
        rules = [r for _l, r, _d in tq.lint_markdown(text)]
        self.assertIn("pipe-in-code-span", rules)
        escaped = text.replace("-name x | wc", r"-name x \| wc")
        self.assertEqual(tq.lint_markdown(escaped), [])

    def test_unclosed_fence_is_caught(self):
        rules = [r for _l, r, _d in tq.lint_markdown("```\nnot a table | x |\n")]
        self.assertEqual(rules, ["unclosed-fence"])

    def test_generated_board_lints_clean(self):
        payload = data([task("a", 1.0, model="glm-5.3"),
                        task("b", 2.0, model="deepseek-v4.1-flash-1017", state="blocked")])
        t = payload["tasks"][0]
        t["notes"] = "a pipe | and a newline\ninside prose"
        rows = tq.board_rows(payload)
        self.assertEqual(tq.lint_markdown("\n".join(rows)), [])

    def test_render_refuses_markdown_it_would_break(self):
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(tq.QueueError):
                tq._emit(["| a | b |", "| 1 | 2 |"], "test table")

    def test_the_board_renders(self):
        """The published board: every table it carries must parse."""
        board = REPO_ROOT / "mad-science" / "STATUS.md"
        self.assertEqual(tq.lint_markdown(board.read_text(encoding="utf-8")), [])

    def test_live_zone_docs_this_guard_owns_render(self):
        # Files this guard fixed and now protects. NOT the whole tree: `attic/` is frozen
        # provenance, and SESSION-RECORD's ledger fragments are mid-table continuations whose
        # header lives elsewhere — minting headers there would rewrite history, not fix it.
        for rel in ("tools/README.md",
                    "recipes/ornith/README.md",
                    "recipes/glm/mods/tensorfold-glm53-3bpw-launcher/README.md"):
            with self.subTest(file=rel):
                path = REPO_ROOT / rel
                self.assertEqual(tq.lint_markdown(path.read_text(encoding="utf-8")), [])
