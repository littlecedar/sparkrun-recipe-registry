#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Travis Wichert
#
# SPDX-License-Identifier: AGPL-3.0-or-later
"""BFCL (Berkeley Function-Calling Leaderboard) tool-calling scorer for a live endpoint.

Why this file exists
--------------------
`sparkrun`'s benchmarking path measures speed (`benchmarking/*.yaml`, `framework:
llama-benchy`), and the repo's quality instruments (`quality-battery.py`,
`qwen4-quality-eval.py`) are in-house exact-match batteries that no published
number is comparable to.  The explore lane's brief is *frontier reasoning +
tool-calling* models, and three of its shortlist entries publish **BFCL** scores
(inclusionAI/Ling-3.0-flash, Aleph-Alpha/Kolibri-1, meta-models/Muse-Glimmer-30B)
— so BFCL is the standard suite this lane needs, and it is the one the lane's
research doc names (`recipes/explore/EXPLORE-MODELS-RESEARCH.md` §4).

This tool runs BFCL v3 questions against an OpenAI-compatible
`/v1/chat/completions` and scores them with a faithful Python port of the
official AST checker (`bfcl_eval/eval_checker/ast_eval/ast_checker.py`,
ShishirPatil/gorilla, AGPL-3.0), so the accuracy number is the leaderboard's
rule rather than a lookalike.

Faithfulness and its one deliberate deviation
---------------------------------------------
**Same questions, same gold answers, same scoring rule.**  The one difference is
the *request shape*: the official harness prompts the model for a BFCL-dialect
function call as text and parses it; this tool sends the functions through the
OpenAI `tools` parameter and reads the structured `message.tool_calls` back.
That is how a vLLM/SGLang serve of these models exposes tools (`--tool-call-parser`)
and how the already-adopted `tool-eval-bench` drives them, so the score is
comparable **in kind** with a published BFCL number, not identical to it: a
server whose template/parser drops the structured call will read as "no call".

Scored categories (v3 file names)
---------------------------------
AST categories, scored by the ported checker:
`simple`, `multiple`, `parallel`, `parallel_multiple`, and their `live_*` twins.
Relevance categories, scored by the official call / no-call rule:
`irrelevance`, `live_irrelevance` (pass iff **no** call), `live_relevance`
(pass iff **some** non-empty call).
Not supported (each needs machinery this tool deliberately omits): `java` /
`javascript` (language-specific type converters), `rest` / `sql` / `exec_*`
(executable, not AST, evaluation), and the `multi_turn_*` categories (stateful
tool execution across turns).  A `--categories` naming one of those is a bad-flag
exit, not a silent skip.

Why it is not just `curl`
-------------------------
Every failure that matters here returns HTTP 200 with plausible content, so the
scoring is exact (function name, required parameters present, no unexpected
parameter, value and **type** matched against the gold answer with BFCL's
case/punctuation standardization), `temperature` is pinned to 0, and the raw
`tool_calls` of every question — pass or fail — are kept and written to `--json`.
A model that emits a plausible-but-wrong call fails; a model that emits no call
fails every AST category (and passes `irrelevance`).

Data
----
The tool reads the official BFCL v3 JSON, revision-pinned to
`gorilla-llm/Berkeley-Function-Calling-Leaderboard@61fc0608` (Apache-2.0).  Fetch
it once on the head node, then point `--data-dir` at the directory:

    hf download gorilla-llm/Berkeley-Function-Calling-Leaderboard \\
        --repo-type dataset --revision 61fc0608cfd831fcfbbaa676ebdfef0ed963eeda \\
        --local-dir ~/bfcl

Command (live endpoint; see tools/README.md for the measured example):

    python3 tools/bfcl-eval.py --base-url http://127.0.0.1:8000 \\
        --data-dir ~/bfcl --categories simple,multiple,parallel,irrelevance \\
        --json bfcl.json

    python3 tools/bfcl-eval.py --selftest     # offline, in-process mock, ~1 s

Exit codes: `0` the run completed (the score is the artifact), `1` no request
completed (endpoint unreachable for every question) or `--fail-under` missed,
`2` bad flags / missing or malformed data files.  A *score*, however low, is not
an error — read it from the JSON.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

# ---------------------------------------------------------------------------
# Official data layout (BFCL v3 file names, gorilla-llm/Berkeley-Function-Calling-Leaderboard)
# ---------------------------------------------------------------------------

DATA_REVISION = "61fc0608cfd831fcfbbaa676ebdfef0ed963eeda"

CATEGORY_FILES = {
    "simple": "BFCL_v3_simple.json",
    "multiple": "BFCL_v3_multiple.json",
    "parallel": "BFCL_v3_parallel.json",
    "parallel_multiple": "BFCL_v3_parallel_multiple.json",
    "irrelevance": "BFCL_v3_irrelevance.json",
    "live_simple": "BFCL_v3_live_simple.json",
    "live_multiple": "BFCL_v3_live_multiple.json",
    "live_parallel": "BFCL_v3_live_parallel.json",
    "live_parallel_multiple": "BFCL_v3_live_parallel_multiple.json",
    "live_irrelevance": "BFCL_v3_live_irrelevance.json",
    "live_relevance": "BFCL_v3_live_relevance.json",
}
DEFAULT_CATEGORIES = ["simple", "multiple", "parallel", "parallel_multiple", "irrelevance"]

# AST-scored (everything else is a relevance/irrelevance call-or-not rule).
AST_CATEGORIES = {
    "simple", "multiple", "parallel", "parallel_multiple",
    "live_simple", "live_multiple", "live_parallel", "live_parallel_multiple",
}
UNSUPPORTED_CATEGORIES = {
    "java", "javascript", "rest", "sql", "chatable",
    "exec_simple", "exec_multiple", "exec_parallel", "exec_parallel_multiple",
    "multi_turn_base", "multi_turn_composite", "multi_turn_long_context",
    "multi_turn_miss_func", "multi_turn_miss_param",
}


def is_relevance_category(category: str) -> bool:
    return "relevance" in category


# ---------------------------------------------------------------------------
# Function-name normalization (mirrors bfcl_eval ast_checker.convert_func_name:
# OpenAI-style APIs forbid "." in a function name, so BFCL rewrites it).
# ---------------------------------------------------------------------------

def sanitize_name(name: str) -> str:
    return name.replace(".", "_")


def sanitize_func(func: dict) -> dict:
    out = dict(func)
    out["name"] = sanitize_name(str(func.get("name", "")))
    return out


def sanitize_answer(ground_truth: list) -> list:
    return [{sanitize_name(k): v for k, v in entry.items()} for entry in ground_truth]


# ---------------------------------------------------------------------------
# BFCL -> OpenAI JSON-Schema conversion (tools payload only).
# ---------------------------------------------------------------------------

_JSON_TYPE = {
    "dict": "object", "tuple": "array", "any": "string",
    "string": "string", "integer": "integer", "float": "number",
    "boolean": "boolean", "array": "array", "number": "number", "object": "object",
}


def to_json_schema(node):
    """Deep-copy a BFCL `parameters` node, mapping BFCL types to JSON Schema.

    BFCL writes `"type": "dict"` where OpenAI expects `"object"`; a server that
    validates the tools payload rejects the payload outright otherwise.
    """
    if isinstance(node, dict):
        out = {k: to_json_schema(v) for k, v in node.items()}
        t = out.get("type")
        if isinstance(t, str) and t in _JSON_TYPE:
            out["type"] = _JSON_TYPE[t]
        return out
    if isinstance(node, list):
        return [to_json_schema(v) for v in node]
    return node


def to_openai_tools(funcs: list) -> list:
    return [
        {
            "type": "function",
            "function": {
                "name": sanitize_name(str(f.get("name", ""))),
                "description": f.get("description", ""),
                "parameters": to_json_schema(f.get("parameters", {"type": "object", "properties": {}})),
            },
        }
        for f in funcs
    ]


# ---------------------------------------------------------------------------
# Official AST checker, ported for the Python path (ast_checker.py, go port of
# the semantics, not of the error strings).  `model_output` is a list of
# `{func_name: {arg: value}}` — exactly BFCL's decoded AST, which is what
# `message.tool_calls` gives us after JSON-parsing the arguments.
# ---------------------------------------------------------------------------

PYTHON_TYPE_MAPPING = {
    "string": str, "integer": int, "float": float, "boolean": bool,
    "array": list, "tuple": list, "dict": dict, "any": str,
}
PYTHON_NESTED_TYPE_CHECK_LIST = ["array", "tuple"]


def find_description(func_descriptions, name):
    for description in func_descriptions:
        if description["name"] == name:
            return description
    return None


def get_possible_answer_type(possible_answer: list):
    for answer in possible_answer:
        if answer != "":  # "" marks an optional parameter
            return type(answer)
    return None


def type_checker(param, value, possible_answer, expected_type_description,
                 expected_type_converted, nested_type_converted):
    result = {"valid": True, "error": [], "is_variable": False,
              "error_type": "type_error:simple"}

    is_variable = False
    possible_answer_type = get_possible_answer_type(possible_answer)
    if possible_answer_type is not None and possible_answer_type != expected_type_converted:
        is_variable = True

    if type(value) == expected_type_converted:
        if nested_type_converted is None:
            result["is_variable"] = is_variable
            return result
        for possible_answer_item in possible_answer:
            flag = True
            if type(possible_answer_item) == list:
                for value_item in value:
                    checker_result = type_checker(
                        param, value_item, possible_answer_item,
                        str(nested_type_converted), nested_type_converted, None,
                    )
                    if not checker_result["valid"]:
                        flag = False
                        break
            if flag:
                return {"valid": True, "error": [], "is_variable": is_variable}
        result["valid"] = False
        result["error"] = [(
            f"Nested type checking failed for parameter {param!r}. Expected outer "
            f"type {expected_type_description} with inner type {nested_type_converted}. "
            f"Parameter value: {value!r}."
        )]
        result["error_type"] = "type_error:nested"
        return result

    possible_answer_type = get_possible_answer_type(possible_answer)
    if possible_answer_type is not None and type(value) == possible_answer_type:
        result["is_variable"] = True
        return result

    result["valid"] = False
    result["error"].append(
        f"Incorrect type for parameter {param!r}. Expected type "
        f"{expected_type_description}, got {type(value).__name__}. Value: {value!r}."
    )
    result["error_type"] = "type_error:simple"
    return result


def standardize_string(input_string: str) -> str:
    """BFCL's value normalization: drop spaces and `,./-_*^`, lower-case,
    and single quotes -> double quotes (so "April 1, 2024" == "april1 2024")."""
    return re.sub(r"[ \,\.\/\-\_\*\^]", "", input_string).lower().replace("'", '"')


def string_checker(param, model_output, possible_answer):
    standardized = standardize_string(model_output)
    allowed = [standardize_string(a) for a in possible_answer if type(a) == str]
    if standardized not in allowed:
        return {"valid": False, "error_type": "value_error:string",
                "error": [f"Invalid value for {param!r}: {model_output!r}. Expected one of {possible_answer}."]}
    return {"valid": True, "error": []}


def list_checker(param, model_output, possible_answer):
    standardized = [standardize_string(v) if type(v) == str else v for v in model_output]
    allowed = [
        [standardize_string(v) if type(v) == str else v for v in answer]
        for answer in possible_answer
    ]
    if standardized not in allowed:
        return {"valid": False, "error_type": "value_error:list/tuple",
                "error": [f"Invalid value for {param!r}: {model_output!r}. Expected one of {possible_answer}."]}
    return {"valid": True, "error": []}


def dict_checker(param, model_output, possible_answers):
    result = {"valid": False, "error": [], "error_type": "dict_checker:unclear"}
    for candidate in possible_answers:
        if candidate == "":
            continue
        result = {"valid": False, "error": [], "error_type": "dict_checker:unclear"}
        flag = True
        for key, value in model_output.items():
            if key not in candidate:
                result["valid"] = False
                result["error_type"] = "value_error:dict_key"
                result["error"].append(f"Unexpected dict key parameter: {key!r}.")
                flag = False
                break
            standard_value = standardize_string(value) if type(value) == str else value
            allowed = [standardize_string(v) if type(v) == str else v for v in candidate[key]]
            if standard_value not in allowed:
                result["valid"] = False
                result["error_type"] = "value_error:dict_value"
                result["error"].append(f"Invalid value for {key!r}: {value!r}. Expected one of {allowed}.")
                flag = False
                break
        for key, value in candidate.items():
            if key not in model_output and "" not in value:
                result["valid"] = False
                result["error_type"] = "value_error:dict_key"
                result["error"].append(f"Missing dict key parameter: {key!r}.")
                flag = False
                break
        if flag:
            return {"valid": True, "error": []}
    return result


def list_dict_checker(param, model_output, possible_answers):
    result = {"valid": False, "error": [], "error_type": "list_dict_checker:unclear"}
    for answer_index in range(len(possible_answers)):
        flag = True
        if len(model_output) != len(possible_answers[answer_index]):
            result = {"valid": False, "error": ["Wrong number of dictionaries in the list."],
                      "error_type": "value_error:list_dict_count"}
            continue
        for dict_index in range(len(model_output)):
            result = dict_checker(param, model_output[dict_index],
                                  [possible_answers[answer_index][dict_index]])
            if not result["valid"]:
                flag = False
                break
        if flag:
            return {"valid": True, "error": []}
    return result


def simple_function_checker(func_description, model_output, possible_answer):
    possible_answer = list(possible_answer.values())[0]
    func_name = func_description["name"]
    param_details = func_description["parameters"]["properties"]
    required_params = func_description["parameters"].get("required", [])

    result = {"valid": True, "error": [], "error_type": "simple_function_checker:unclear"}

    if func_name not in model_output:
        return {"valid": False, "error_type": "simple_function_checker:wrong_func_name",
                "error": [f"Function name {func_name!r} not found in model output."]}

    model_params = model_output[func_name]

    for param in required_params:
        if param not in model_params:
            return {"valid": False, "error_type": "simple_function_checker:missing_required",
                    "error": [f"Missing required parameter: {param!r}."]}

    for param, value in model_params.items():
        if param not in param_details or param not in possible_answer:
            return {"valid": False, "error_type": "simple_function_checker:unexpected_param",
                    "error": [f"Unexpected parameter: {param!r}."]}

        expected_type_description = param_details[param]["type"]
        is_variable = False
        nested_type_converted = None

        expected_type_converted = PYTHON_TYPE_MAPPING[expected_type_description]
        if expected_type_description in PYTHON_NESTED_TYPE_CHECK_LIST:
            nested_type = param_details[param]["items"]["type"]
            nested_type_converted = PYTHON_TYPE_MAPPING[nested_type]

        if expected_type_description == "tuple" and type(value) == tuple:
            value = list(value)
        if expected_type_description == "float" and type(value) == int:
            value = float(value)

        type_check_result = type_checker(
            param, value, possible_answer[param],
            expected_type_description, expected_type_converted, nested_type_converted,
        )
        is_variable = type_check_result["is_variable"]
        if not type_check_result["valid"]:
            return type_check_result

        if not is_variable:
            if expected_type_converted == dict:
                result = dict_checker(param, value, possible_answer[param])
                if not result["valid"]:
                    return result
                continue
            if expected_type_converted == list and nested_type_converted == dict:
                result = list_dict_checker(param, value, possible_answer[param])
                if not result["valid"]:
                    return result
                continue
            if expected_type_converted == str:
                result = string_checker(param, value, possible_answer[param])
                if not result["valid"]:
                    return result
                continue
            if expected_type_converted == list:
                result = list_checker(param, value, possible_answer[param])
                if not result["valid"]:
                    return result
                continue

        if value not in possible_answer[param]:
            return {"valid": False, "error_type": "value_error:others",
                    "error": [f"Invalid value for {param!r}: {value!r}. Expected one of {possible_answer[param]}."]}

    for param in possible_answer:
        if param not in model_params and "" not in possible_answer[param]:
            return {"valid": False, "error_type": "simple_function_checker:missing_optional",
                    "error": [f"Optional parameter {param!r} not provided and not marked as optional."]}

    return result


def parallel_function_checker_no_order(func_descriptions, model_output, possible_answers):
    if len(model_output) != len(possible_answers):
        return {"valid": False, "error_type": "parallel_function_checker_no_order:wrong_count",
                "error": ["Wrong number of functions."]}

    matched_indices = []
    for i in range(len(possible_answers)):
        func_name_expected = list(possible_answers[i].keys())[0]
        func_description = find_description(func_descriptions, func_name_expected)
        all_errors = []
        matched = False
        for index in range(len(model_output)):
            if index in matched_indices:
                continue
            result = simple_function_checker(func_description, model_output[index], possible_answers[i])
            if result["valid"]:
                matched_indices.append(index)
                matched = True
                break
            all_errors.append({f"model_result_index_{index}": result["error"]})
        if not matched:
            return {"valid": False, "error_type": "parallel_function_checker_no_order:cannot_find_match",
                    "error": [f"No model output matched possible answer {i}."] + all_errors}
    return {"valid": True, "error": []}


def multiple_function_checker(func_descriptions, model_output, possible_answers):
    if len(model_output) != len(possible_answers):
        return {"valid": False, "error_type": "multiple_function_checker:wrong_count",
                "error": ["Wrong number of functions."]}
    func_name_expected = list(possible_answers[0].keys())[0]
    func_description = find_description(func_descriptions, func_name_expected)
    return simple_function_checker(func_description, model_output[0], possible_answers[0])


def ast_checker(func_descriptions, model_output, possible_answers, test_category):
    if "parallel" in test_category:
        return parallel_function_checker_no_order(func_descriptions, model_output, possible_answers)
    if "multiple" in test_category:
        return multiple_function_checker(func_descriptions, model_output, possible_answers)
    if len(model_output) != 1:
        return {"valid": False, "error_type": "simple_function_checker:wrong_count",
                "error": ["Wrong number of functions."]}
    return simple_function_checker(func_descriptions[0], model_output[0], possible_answers[0])


# ---------------------------------------------------------------------------
# Model-output extraction: OpenAI tools -> BFCL AST.
# ---------------------------------------------------------------------------

class CallParseError(ValueError):
    """The reply carried a function call whose arguments could not be read."""


class UnsupportedContent(ValueError):
    """The question needs a modality (e.g. an image) this tool does not send."""


def extract_calls(message: dict) -> list:
    """Return the reply as BFCL AST: [{func_name: {arg: value}}, ...]."""
    calls = []
    for tool_call in (message.get("tool_calls") or []):
        function = tool_call.get("function") or {}
        name = function.get("name")
        if not name:
            continue
        arguments = function.get("arguments")
        if isinstance(arguments, str):
            if not arguments.strip():
                arguments = {}
            else:
                try:
                    arguments = json.loads(arguments)
                except (json.JSONDecodeError, ValueError) as exc:
                    raise CallParseError(f"unreadable tool-call arguments: {arguments!r}") from exc
        if not isinstance(arguments, dict):
            raise CallParseError(f"tool-call arguments are not an object: {arguments!r}")
        calls.append({sanitize_name(str(name)): arguments})

    if calls:
        return calls

    # Fallback: some templates/parsers leave the call in `content` as JSON.
    content = message.get("content")
    if isinstance(content, str) and content.strip():
        text = content.strip()
        if text.startswith("```"):
            text = re.sub(r"^```[a-zA-Z]*\n?|\n?```$", "", text).strip()
        try:
            parsed = json.loads(text)
        except (json.JSONDecodeError, ValueError):
            return []
        if isinstance(parsed, dict) and "name" in parsed:
            return extract_calls({"tool_calls": [
                {"function": {"name": parsed.get("name"), "arguments": parsed.get("arguments", {})}}]})
        items = parsed if isinstance(parsed, list) else [parsed]
        tool_calls = []
        for item in items:
            if not isinstance(item, dict):
                return []
            if "name" in item:
                tool_calls.append({"function": {"name": item.get("name"),
                                                "arguments": item.get("arguments", {})}})
            else:  # a plain {func_name: args} object
                tool_calls.extend({"function": {"name": k, "arguments": v}}
                                  for k, v in item.items())
        return extract_calls({"tool_calls": tool_calls})
    return []


def flatten_content(content) -> str:
    """Single-turn text of a BFCL message; a non-text part is unsupported."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        texts = []
        for part in content:
            if isinstance(part, dict) and part.get("type") == "text":
                texts.append(part.get("text", ""))
            elif isinstance(part, str):
                texts.append(part)
            else:
                raise UnsupportedContent(
                    f"question carries a non-text content part ({type(part).__name__}); "
                    "this tool sends text only"
                )
        return " ".join(texts)
    raise UnsupportedContent(f"unrecognized content type: {type(content).__name__}")


# ---------------------------------------------------------------------------
# Scoring one entry.
# ---------------------------------------------------------------------------

def score_entry(category, checker_funcs, possible_answers, calls):
    """(valid, error_type, error) for one question under the official rule."""
    if is_relevance_category(category):
        if "irrelevance" in category:
            valid = len(calls) == 0
            return valid, ("" if valid else "irrelevance_error:decoder_success"), (
                [] if valid else ["Emitted a function call for an irrelevant question."])
        valid = len(calls) > 0
        return valid, ("" if valid else "relevance_error:decoder_failed"), (
            [] if valid else ["Emitted no function call for a relevant question."])
    result = ast_checker(checker_funcs, calls, possible_answers, category)
    return bool(result["valid"]), result.get("error_type", ""), result.get("error", [])


# ---------------------------------------------------------------------------
# Data loading.
# ---------------------------------------------------------------------------

class DataError(ValueError):
    """The --data-dir does not hold the expected official BFCL files."""


def load_jsonl(path: Path) -> list:
    if not path.is_file():
        raise DataError(f"missing BFCL data file: {path}")
    records = []
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise DataError(f"{path}:{lineno}: not JSON") from exc
    if not records:
        raise DataError(f"{path}: parsed to zero records (a missing parse must never pass)")
    return records


def load_category(data_dir: Path, category: str, limit=None) -> list:
    """Return [{category, id, question, answer}] for one BFCL category."""
    questions = load_jsonl(data_dir / CATEGORY_FILES[category])
    answers = {}
    answer_path = data_dir / "possible_answer" / CATEGORY_FILES[category]
    if answer_path.is_file():
        for entry in load_jsonl(answer_path):
            answers[entry["id"]] = entry

    entries = []
    for question in questions:
        entries.append({
            "category": category,
            "id": question["id"],
            "question": question,
            "answer": answers.get(question["id"]),
        })
    if limit is not None:
        entries = entries[:limit]
    return entries


# ---------------------------------------------------------------------------
# Endpoint client.
# ---------------------------------------------------------------------------

def post_json(url: str, body: dict, api_key=None, timeout=600) -> dict:
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    request = urllib.request.Request(url, data=json.dumps(body).encode(), headers=headers)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.load(response)


def resolve_model(base_url: str, model, api_key=None, timeout=30) -> str:
    if model:
        return model
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    request = urllib.request.Request(base_url.rstrip("/") + "/v1/models", headers=headers)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        data = json.load(response)
    return data["data"][0]["id"]


def ask(base_url, model, messages, tools, tool_choice, max_tokens, api_key, timeout) -> dict:
    body = {
        "model": model,
        "messages": messages,
        "temperature": 0,
        "max_tokens": max_tokens,
    }
    if tools:
        body["tools"] = tools
        body["tool_choice"] = tool_choice
    response = post_json(base_url.rstrip("/") + "/v1/chat/completions", body, api_key, timeout)
    return response["choices"][0]["message"]


# ---------------------------------------------------------------------------
# Runner.
# ---------------------------------------------------------------------------

def run(entries, base_url, model, tool_choice="auto", max_tokens=512,
        api_key=None, timeout=600, quiet=False, ask_fn=None):
    ask_fn = ask_fn or (
        lambda messages, tools: ask(base_url, model, messages, tools, tool_choice,
                                    max_tokens, api_key, timeout)
    )
    records = []
    completed = 0
    for entry in entries:
        category = entry["category"]
        question = entry["question"]
        checker_funcs = [sanitize_func(f) for f in question.get("function", [])]
        tools = to_openai_tools(checker_funcs)
        possible_answers = (
            sanitize_answer(entry["answer"]["ground_truth"]) if entry["answer"] else []
        )

        record = {"id": entry["id"], "category": category, "calls": [],
                  "valid": False, "error_type": "", "error": [], "latency_s": None}
        try:
            messages = [
                {"role": m["role"], "content": flatten_content(m.get("content"))}
                for m in question["question"][0]
            ]
        except UnsupportedContent as exc:
            record["error_type"] = "unsupported_content"
            record["error"] = [str(exc)]
            records.append(record)
            continue

        started = time.time()
        try:
            message = ask_fn(messages, tools)
        except (urllib.error.URLError, OSError, ValueError) as exc:
            record["error_type"] = "transport_error"
            record["error"] = [f"{type(exc).__name__}: {exc}"]
            records.append(record)
            continue
        record["latency_s"] = round(time.time() - started, 3)
        completed += 1

        record["message"] = message
        try:
            calls = extract_calls(message)
        except CallParseError as exc:
            record["error_type"] = "call_parse_error"
            record["error"] = [str(exc)]
            records.append(record)
            continue
        record["calls"] = calls
        valid, error_type, error = score_entry(category, checker_funcs, possible_answers, calls)
        record["valid"] = valid
        record["error_type"] = error_type
        record["error"] = error

        if not quiet:
            print(f"  [{'PASS' if valid else 'FAIL'}] {entry['id']} ({category})"
                  + ("" if valid else f"  {error_type}"))
        records.append(record)
    return {"records": records, "completed": completed}


def category_summary(records) -> dict:
    summary = {}
    for record in records:
        bucket = summary.setdefault(record["category"], {"correct": 0, "total": 0})
        bucket["total"] += 1
        bucket["correct"] += 1 if record["valid"] else 0
    for bucket in summary.values():
        bucket["accuracy"] = (bucket["correct"] / bucket["total"]) if bucket["total"] else 0.0
    return summary


# ---------------------------------------------------------------------------
# Offline self-test: an in-process mock endpoint with a failure control.
# ---------------------------------------------------------------------------

_FIXTURE_QUESTIONS = {
    "simple": [
        {
            "id": "simple_0",
            "question": [[{"role": "user", "content": "Area of a triangle with base 10 and height 5."}]],
            "function": [{
                "name": "calculate_triangle_area",
                "description": "Calculate the area of a triangle.",
                "parameters": {"type": "dict", "properties": {
                    "base": {"type": "integer"}, "height": {"type": "integer"},
                    "unit": {"type": "string"}}, "required": ["base", "height"]},
            }],
        },
        {
            "id": "simple_1",
            "question": [[{"role": "user", "content": "Calculate the factorial of 5."}]],
            "function": [{
                "name": "math.factorial",
                "description": "Factorial of a number.",
                "parameters": {"type": "dict", "properties": {
                    "number": {"type": "integer"}}, "required": ["number"]},
            }],
        },
    ],
    "multiple": [
        {
            "id": "multiple_0",
            "question": [[{"role": "user", "content": "What is the weather in Paris?"}]],
            "function": [
                {"name": "get_weather", "description": "Weather.",
                 "parameters": {"type": "dict", "properties": {"city": {"type": "string"}},
                                "required": ["city"]}},
                {"name": "get_stock_price", "description": "Stock price.",
                 "parameters": {"type": "dict", "properties": {"ticker": {"type": "string"}},
                                "required": ["ticker"]}},
            ],
        },
    ],
    "parallel": [
        {
            "id": "parallel_0",
            "question": [[{"role": "user", "content": "Play Taylor Swift for 20, then Maroon 5 for 15."}]],
            "function": [{
                "name": "play_music", "description": "Play music.",
                "parameters": {"type": "dict", "properties": {
                    "artist": {"type": "string"}, "duration": {"type": "integer"}},
                    "required": ["artist", "duration"]},
            }],
        },
    ],
    "irrelevance": [
        {
            "id": "irrelevance_0",
            "question": [[{"role": "user", "content": "Find the sum of 3 and 4."}]],
            "function": [{
                "name": "determine_body_mass_index", "description": "BMI.",
                "parameters": {"type": "dict", "properties": {
                    "weight": {"type": "float"}, "height": {"type": "float"}},
                    "required": ["weight", "height"]},
            }],
        },
    ],
}

_FIXTURE_ANSWERS = {
    "simple": [
        {"id": "simple_0", "ground_truth": [
            {"calculate_triangle_area": {"base": [10], "height": [5], "unit": ["units", ""]}}]},
        {"id": "simple_1", "ground_truth": [{"math.factorial": {"number": [5]}}]},
    ],
    "multiple": [
        {"id": "multiple_0", "ground_truth": [{"get_weather": {"city": ["Paris"]}}]},
    ],
    "parallel": [
        {"id": "parallel_0", "ground_truth": [
            {"play_music": {"artist": ["Taylor Swift"], "duration": [20]}},
            {"play_music": {"artist": ["Maroon 5"], "duration": [15]}}]},
    ],
}

# What the mock endpoint answers for each question, keyed by user content.
_CORRECT_CALLS = {
    "Area of a triangle with base 10 and height 5.": [{"calculate_triangle_area": {"base": 10, "height": 5}}],
    "Calculate the factorial of 5.": [{"math.factorial": {"number": 5}}],
    "What is the weather in Paris?": [{"get_weather": {"city": "Paris"}}],
    "Play Taylor Swift for 20, then Maroon 5 for 15.": [
        {"play_music": {"artist": "Taylor Swift", "duration": 20}},
        {"play_music": {"artist": "Maroon 5", "duration": 15}},
    ],
}


def _fixture_entries():
    entries = []
    for category, questions in _FIXTURE_QUESTIONS.items():
        answers = {a["id"]: a for a in _FIXTURE_ANSWERS.get(category, [])}
        for question in questions:
            entries.append({"category": category, "id": question["id"],
                            "question": question, "answer": answers.get(question["id"])})
    return entries


def _mock_ask(mode: str):
    def ask_fn(messages, tools):
        text = messages[-1]["content"]
        calls = _CORRECT_CALLS.get(text, [])
        if mode == "wrong_name" and calls:
            first = calls[0]
            name = next(iter(first))
            calls = [{"totally_wrong_name": first[name]}] + calls[1:]
        elif mode == "wrong_value" and calls:
            first = calls[0]
            name = next(iter(first))
            params = dict(first[name])
            key = next(iter(params))
            params[key] = "wrongval"
            calls = [{name: params}] + calls[1:]
        elif mode == "empty":
            calls = []
        elif mode == "hallucinate":
            calls = [{"determine_body_mass_index": {"weight": 70.0, "height": 1.8}}]
        return {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {"id": f"call_{i}", "type": "function",
                 "function": {"name": name, "arguments": json.dumps(params)}}
                for i, call in enumerate(calls) for name, params in call.items()
            ],
        }
    return ask_fn


def selftest() -> int:
    """Run the whole ladder against in-process mocks; raise AssertionError on a
    control that does not land.  Returns 0 on success."""
    entries = _fixture_entries()
    call_entries = [e for e in entries if e["category"] != "irrelevance"]
    irrelevance_entries = [e for e in entries if e["category"] == "irrelevance"]

    def accuracy(records):
        done = [r for r in records if r["error_type"] != "transport_error"]
        return sum(1 for r in done if r["valid"]) / len(done) if done else 0.0

    # ---- control 1: the correct calls must score 100 %, every category
    result = run(entries, "", "", quiet=True, ask_fn=_mock_ask("correct"))
    summary = category_summary(result["records"])
    for category, bucket in summary.items():
        assert bucket["accuracy"] == 1.0, f"correct mock failed {category}: {bucket}"
    assert accuracy(result["records"]) == 1.0

    # ---- control 2: a wrong function name must fail every AST category
    result = run(call_entries, "", "", quiet=True, ask_fn=_mock_ask("wrong_name"))
    assert accuracy(result["records"]) == 0.0, "wrong-name mock was not rejected"

    # ---- control 3: a wrong value (and wrong type) must fail every AST category
    result = run(call_entries, "", "", quiet=True, ask_fn=_mock_ask("wrong_value"))
    assert accuracy(result["records"]) == 0.0, "wrong-value mock was not rejected"

    # ---- control 4: a silent model fails the AST categories and passes irrelevance
    result = run(call_entries, "", "", quiet=True, ask_fn=_mock_ask("empty"))
    assert accuracy(result["records"]) == 0.0, "empty-output mock was not rejected"
    result = run(irrelevance_entries, "", "", quiet=True, ask_fn=_mock_ask("empty"))
    assert accuracy(result["records"]) == 1.0, "silent model should pass irrelevance"

    # ---- control 5: a call on an irrelevant question must fail
    result = run(irrelevance_entries, "", "", quiet=True, ask_fn=_mock_ask("hallucinate"))
    assert accuracy(result["records"]) == 0.0, "a call on irrelevance was not rejected"

    # ---- control 6: the pieces the mocks do not isolate
    assert standardize_string("April 1, 2024") == standardize_string("april1 2024")
    assert standardize_string("spark.run") != standardize_string("sparkrun_x")
    assert to_json_schema({"type": "dict"}) == {"type": "object"}

    # optional parameter omitted, and parallel answered out of order
    checker_funcs = [sanitize_func(f) for f in _FIXTURE_QUESTIONS["parallel"][0]["function"]]
    answers = sanitize_answer(_FIXTURE_ANSWERS["parallel"][0]["ground_truth"])
    reversed_calls = [{"play_music": {"artist": "Maroon 5", "duration": 15}},
                      {"play_music": {"artist": "Taylor Swift", "duration": 20}}]
    valid, _, _ = score_entry("parallel", checker_funcs, answers, reversed_calls)
    assert valid, "parallel scoring must be order-independent"
    extra = reversed_calls + [{"play_music": {"artist": "X", "duration": 1}}]
    assert not score_entry("parallel", checker_funcs, answers, extra)[0]

    # name normalization: a dotted gold name matches a sanitized model name
    funcs = [sanitize_func(f) for f in _FIXTURE_QUESTIONS["simple"][1]["function"]]
    ans = sanitize_answer(_FIXTURE_ANSWERS["simple"][1]["ground_truth"])
    assert score_entry("simple", funcs, ans, [{"math_factorial": {"number": 5}}])[0]
    assert not score_entry("simple", funcs, ans, [{"math_factorial": {"number": "5"}}])[0]

    print("selftest: all controls passed (correct=100%, wrong-name/wrong-value/empty=0%, "
          "irrelevance inverted)")
    return 0


# ---------------------------------------------------------------------------
# CLI.
# ---------------------------------------------------------------------------

def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Score BFCL v3 tool-calling questions against an OpenAI-compatible "
                    "/v1/chat/completions (faithful AST-checker port).")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000",
                        help="OpenAI-compatible endpoint (default http://127.0.0.1:8000)")
    parser.add_argument("--model", default=None,
                        help="served model id; resolved from /v1/models if omitted")
    parser.add_argument("--data-dir", default=None,
                        help="directory holding the official BFCL v3 .json files "
                             "(see the module docstring for the `hf download` line)")
    parser.add_argument("--categories", default=",".join(DEFAULT_CATEGORIES),
                        help="comma-separated BFCL categories (default: %(default)s)")
    parser.add_argument("--tool-choice", default="auto", choices=["auto", "required", "none"],
                        help="OpenAI tool_choice sent with the tools (default auto)")
    parser.add_argument("--limit", type=int, default=None,
                        help="run only the first N questions of each category")
    parser.add_argument("--max-tokens", type=int, default=512)
    parser.add_argument("--timeout", type=int, default=600)
    parser.add_argument("--api-key", default=None)
    parser.add_argument("--json", default=None, help="write the full result JSON here")
    parser.add_argument("--fail-under", type=float, default=0.0,
                        help="exit 1 if overall pct < PCT (0 disables; release gate)")
    parser.add_argument("--selftest", action="store_true",
                        help="run the offline self-test (no endpoint needed)")
    args = parser.parse_args(argv)

    if args.selftest:
        return selftest()

    if not args.data_dir:
        print("error: --data-dir is required (see the module docstring for the "
              "`hf download` command)", file=sys.stderr)
        return 2

    categories = [c.strip() for c in args.categories.split(",") if c.strip()]
    for category in categories:
        if category in UNSUPPORTED_CATEGORIES or category not in CATEGORY_FILES:
            print(f"error: unsupported BFCL category {category!r}; supported: "
                  f"{', '.join(sorted(CATEGORY_FILES))}", file=sys.stderr)
            return 2

    data_dir = Path(args.data_dir)
    try:
        entries = []
        for category in categories:
            entries.extend(load_category(data_dir, category, args.limit))
    except DataError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    try:
        model = resolve_model(args.base_url, args.model, args.api_key)
    except (urllib.error.URLError, OSError, ValueError, KeyError) as exc:
        print(f"error: could not resolve a model from {args.base_url}: {exc}", file=sys.stderr)
        return 1

    print(f"BFCL v3 @ {DATA_REVISION[:12]}  endpoint={args.base_url}  model={model}"
          f"  categories={','.join(categories)}  questions={len(entries)}")
    result = run(entries, args.base_url, model, tool_choice=args.tool_choice,
                 max_tokens=args.max_tokens, api_key=args.api_key, timeout=args.timeout)
    records = result["records"]

    summary = category_summary(records)
    print("\ncategory                correct/total    accuracy")
    for category in categories:
        bucket = summary.get(category)
        if bucket:
            print(f"  {category:<20} {bucket['correct']:>5}/{bucket['total']:<6} "
                  f"{bucket['accuracy'] * 100:>7.1f}%")

    scored = [r for r in records if r["error_type"] not in ("transport_error", "unsupported_content")]
    correct = sum(1 for r in scored if r["valid"])
    overall = (correct / len(scored) * 100) if scored else 0.0
    errors = sum(1 for r in records if r["error_type"] == "transport_error")
    skipped = sum(1 for r in records if r["error_type"] == "unsupported_content")
    print(f"\nTOTAL {correct}/{len(scored)} = {overall:.1f}%"
          + (f"  ({errors} transport errors)" if errors else "")
          + (f"  ({skipped} unsupported-content questions skipped)" if skipped else ""))
    print("\nA score is not proof of quality: it is one instrument on one endpoint. "
          "Run it twice — a reasoning-capable server is not bitwise-stable across batch "
          "composition even at temperature 0; diff the per-question records in --json.")

    if args.json:
        artifact = {
            "suite": "bfcl-v3",
            "data_revision": DATA_REVISION,
            "data_dir": str(data_dir),
            "base_url": args.base_url,
            "model": model,
            "categories": categories,
            "tool_choice": args.tool_choice,
            "summary": summary,
            "overall": {"correct": correct, "total": len(scored), "pct": overall},
            "transport_errors": errors,
            "skipped_unsupported": skipped,
            "records": records,
        }
        with open(args.json, "w", encoding="utf-8") as handle:
            json.dump(artifact, handle, indent=1)
        print(f"wrote {args.json}")

    if result["completed"] == 0:
        return 1
    if args.fail_under and overall < args.fail_under:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
