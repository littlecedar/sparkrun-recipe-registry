#!/usr/bin/env python3
r"""humanizer 12B — §7(c) acceptance measurement (stdlib only).

Recovered verbatim from the 2026-10-14 receipt `~/benchmarks/humanizer-20261014/`
(measure.py) so the 2026-10-22 quant round is apples-to-apples with the archived
bf16 arm (0 fact losses / 40 rewrites). Provenance header only; the instrument
logic is unchanged.

Boots the recipe on one node, then for a fixed 20-draft set across genres
x 2 samples calls POST /v1/completions with the byte-exact prompt from
prompt_format.json (instr + "\n\n" + draft.strip() + sep) and reports:

  * fact-diff count  — numbers / dates / names in the draft that do not
                       survive into the rewrite (heuristic, documented below)
  * formatting-drop  — structural elements (paragraph breaks, bullets,
                       headings) present in the draft and absent in the rewrite
  * wall-clock per 1k output tokens — from the response's usage block

Usage:  python3 tools/humanizer-measure.py [--url http://127.0.0.1:8000]
        [--model jialinyyzz/humanizer-GGUF] [--samples 2] [--out results.json]

Fact-diff heuristic (an approximation, not the card's LLM judge):
  numbers : re.findall(r"\d[\d,\.]*%?") with "," stripped
  dates   : English month names + weekday names + 4-digit years (years are
            already numbers, kept here so a dropped "March" still counts)
  names   : capitalised multi-word sequences (e.g. "Meridian Bank") and
            capitalised words appearing mid-sentence (not after ". " or a
            newline). Sentence-initial words are skipped because a rewrite is
            allowed to reorder sentences.
"""
import argparse
import hashlib
import json
import re
import time
import urllib.request

PROMPT_FORMAT = {
    "instr": (
        "Rewrite the text below so it reads like a person wrote it, not a "
        "language model.\n\nReorganize it as you see fit. Vary sentence length "
        "on purpose. Cut hedging,\nthroat-clearing, and any sentence that only "
        "announces what comes next.\nPrefer the concrete word over the abstract "
        "one. It is fine to sound uneven.\n\nEvery fact, number, unit, date, "
        "name and quotation must survive unchanged."
    ),
    "sep": "\n\n### Rewritten:\n\n",
    "fingerprint": "cc51d66b4c593fbe",
}

DRAFTS = [
    # 1 work email
    ("email", "Hi Nadia,\n\nI'm handing off the Meridian Bank loan audit to you. We've completed the review of 88 files, with 12 files remaining. The outstanding files are in the \"Pending Review\" folder in the Meridian Bank audit workspace, organized by borrower name.\n\nThe remaining items are primarily commercial real estate loans and include several files requiring confirmation of updated income statements, collateral valuations, and covenant documentation. I've flagged the missing items in the audit tracker and added notes for the files that may need follow-up with Meridian Bank's loan operations team.\n\nThe deadline is Friday, March 14. Please prioritize the files marked \"High\" in the tracker, especially MB-2047, MB-2091, and MB-2110, since those are scheduled for management review first. I'll be available through Wednesday afternoon to answer questions or provide context on any earlier decisions.\n\nThanks for taking this over."),
    # 2 essay
    ("essay", "The case for quieter cities is usually made in terms of noise. That is the smallest part of it. When Oslo pedestrianized its centre in 2019, measured traffic noise on Karl Johans gate fell by 8 decibels, and the city's own report credits the change with a 12 percent rise in evening foot traffic over two years.\n\nThe larger effect is on attention. A street that expects you to move at 30 km/h asks for a different kind of noticing than one that expects 5. Retailers on Strøget in Copenhagen reported that shoppers spent roughly 20 percent more time per visit after the street was closed to cars in 1962, a figure that has been cited, re-cited, and quietly disputed for sixty years.\n\nNone of this is an argument against cars. It is an argument against letting a single mode of transport set the terms for everything else."),
    # 3 project report with headings and bullets
    ("report", "# Q3 Platform Reliability Report\n\n## Summary\n\nAvailability for the quarter came in at 99.94 percent against a target of 99.95. Two incidents in August account for the shortfall.\n\n## Incidents\n\n- INC-4471 (August 6): a bad configuration push to the billing service took 41 minutes to detect. Root cause was a missing schema check in the deploy pipeline. Owner: Priya Raghavan.\n- INC-4488 (August 19): storage saturation on node eu-west-3c degraded checkout for 26 minutes. The cluster had been running at 91 percent capacity since July 28.\n\n## Actions\n\n1. Add schema validation to the deploy pipeline (due October 1, owner Priya Raghavan).\n2. Raise the storage headroom alarm threshold to 75 percent (due September 20, owner Tomas Lindqvist).\n\n## Cost\n\nInfrastructure spend was 214,000 EUR, 6 percent under budget."),
    # 4 forum post
    ("forum", "Posted this after a week of fighting the same problem, in case it saves someone else the time.\n\nThe short version: if your inverter reports 0 W at sunrise but the battery is at 63 percent, check the DC isolator before you touch anything else. Mine had a hairline crack that only opened up below about 4 degrees Celsius.\n\nI wasted two days on firmware. I rolled back from 2.4.1 to 2.3.9 and then to 2.2.0, reinstalled the monitoring agent twice, and replaced the RS-485 cable. None of it mattered. The electrician found the crack in eleven minutes with a torch and a can of cold spray.\n\nIf you are in the northern hemisphere and this starts in late October, that is your tell."),
    # 5 internal memo
    ("memo", "MEMORANDUM\n\nTo: All Engineering Staff\nFrom: Dana Whitfield, VP Engineering\nDate: September 2, 2026\nSubject: Change to the on-call rotation\n\nStarting October 1, the primary on-call rotation moves from weekly to daily blocks. Secondary on-call stays weekly.\n\nThe change follows the review of 14 pages over the last two quarters. Median time-to-acknowledge was 19 minutes on week-long rotations and 6 minutes on the two pilot teams that used daily blocks. The pilot ran from April 7 to June 30 with 22 engineers.\n\nShift handover is at 10:00 local time. The rotation tool will be updated on September 25; until then, keep using the old schedule. Questions to Dana Whitfield or to your team lead."),
    # 6 blog post
    ("blog", "## Why we stopped caching our model weights\n\nWe ran the numbers last month and the answer was embarrassing.\n\nOur image cache saved us 340 GB of egress in August, which sounds good until you look at what it cost. The cache nodes ran three instances of Ceph, and those instances accounted for 41 percent of our total compute bill. In dollar terms: 3,900 USD saved on transfer, 11,200 USD spent on serving.\n\nWe turned it off on September 8. Latency went from a p50 of 210 ms to 265 ms, which nobody has complained about yet. The egress bill for September is tracking to about 4,100 USD.\n\nIf your workload is bursty and your origin is fast, measure before you cache. We did not."),
    # 7 product description
    ("product", "The Kestrel 400 is a 400 W portable power station that weighs 5.4 kg and fits under an airline seat in its carry case.\n\nIt holds 384 Wh, charges from a wall outlet in 70 minutes, and from a 200 W solar panel in about 3 hours of full sun. The inverter is pure sine wave at 120 V and handles surge loads to 800 W for 3 seconds, which is enough to start a small fridge compressor.\n\nPorts: two AC outlets, one 100 W USB-C, two 18 W USB-A, and a 12 V car socket. The battery is rated for 3,000 cycles to 80 percent capacity. Warranty is 5 years.\n\nAvailable in March 2027 at 449 USD."),
    # 8 cover letter
    ("cover_letter", "Dear Ms. Okonkwo,\n\nI am writing to apply for the Data Platform Engineer role advertised on your careers page on August 28.\n\nFor the past four years I have worked at Helixon Labs, where I own the ingestion pipeline for about 900 million events a day. In 2025 I led the migration from a single Postgres cluster to a partitioned setup, which cut query p95 from 4.2 seconds to 380 milliseconds and reduced our monthly database bill by 31 percent.\n\nI have worked mainly in Python and Go, with some Rust for the hot path. I hold a BSc in Computer Science from the University of Leeds, awarded in 2021.\n\nI would welcome the chance to discuss the role. I can be reached at 555-0134 or by email.\n\nSincerely,\nMarcus Feld"),
    # 9 incident writeup
    ("incident", "Incident INC-4488 — checkout degradation on eu-west-3c\n\nDetected: August 19, 14:07 UTC (alert: checkout_error_rate > 2 percent)\nResolved: August 19, 14:33 UTC\nDuration: 26 minutes\n\nImpact: 3,140 checkout attempts failed, affecting an estimated 1,870 customers. Gross revenue impact was 92,400 EUR.\n\nTimeline. At 13:58 the storage cluster on eu-west-3c crossed 91 percent utilisation. At 14:01 the checkout service's write latency rose from 12 ms to 1,900 ms. Paging fired at 14:07. Tomas Lindqvist identified the saturation at 14:12 and began draining the read replica. Service recovered at 14:33.\n\nRoot cause: capacity growth had not been alarmed on since July 28. The usable headroom was 9 percent against an internal standard of 25 percent."),
    # 10 meeting notes with bullets
    ("meeting_notes", "Design review — Atlas ingestion v2\nAttendees: Priya Raghavan, Tomas Lindqvist, Sofia Meier, Ben Adeyemi\nDate: October 2, 2026, 15:00-16:10\n\nDecisions\n- We will keep the Kafka topic as the source of truth and add a compacted mirror for replay.\n- Retention moves from 7 days to 30 days, starting November 3.\n- Sofia Meier owns the schema registry migration.\n\nOpen questions\n1. Do we need exactly-once guarantees across the mirror boundary, or is at-least-once acceptable? Ben Adeyemi to write up by October 9.\n2. What is the disk budget for 30 days at current volume — roughly 4.1 TB, or 1.2 TB if we compress?\n\nNext meeting: October 16, same time."),
    # 11 press release
    ("press_release", "FOR IMMEDIATE RELEASE\n\nLittle Cedar Group Opens Second Facility in Bristol\n\nBRISTOL, October 5, 2026 — Little Cedar Group today announced the opening of a second engineering facility in Bristol, creating 60 jobs over the next 18 months. The site will focus on inference infrastructure for on-premise AI systems.\n\n\"We looked at eleven cities and Bristol won on the strength of its university pipeline,\" said Ada Ferreira, chief executive. The company expects to hire 25 people by March 2027.\n\nThe facility occupies 1,400 square metres at the Temple Quarter campus. Little Cedar Group was founded in 2019 and employs 210 people across two countries."),
    # 12 tutorial with headings
    ("tutorial", "## Replacing a bike bottom bracket in an afternoon\n\nYou need a 16-notch tool, a torque wrench, and about 90 minutes.\n\n### Remove the cranks\n\nTake out the 8 mm crank bolt on each side. On most modern bikes the left arm needs a 10 mm hex, not an 8. Do not hammer the arm off; use the puller.\n\n### Pull the old bracket\n\nThread the tool fully in before you turn it. A Shimano Hollowtech II cup takes about 40 Nm to break loose and feels unnerving the first time.\n\n### Fit the new one\n\nGrease the threads. Drive the right cup to 35 Nm, then the left to 35 Nm. Re-check both after 100 km."),
    # 13 policy summary
    ("policy", "Remote Work Policy — Summary\n\nEffective January 6, 2027, employees may work remotely up to three days per week, subject to manager approval. Fully remote arrangements require sign-off from a director.\n\nCore hours are 10:00 to 15:00 in the employee's local time. Outside those hours, schedules are flexible. Employees must maintain a home connection of at least 50 Mbps down and 10 Mbps up.\n\nEquipment: the company provides a laptop and a 200 USD annual allowance for peripherals. Home office expenses are not otherwise reimbursed. Employees working remotely more than two days per week must complete the data handling module (module 4B) by February 28, 2027."),
    # 14 review
    ("review", "I bought this kettle in July and used it daily for four months.\n\nIt boils 1.5 litres in about 4 minutes 20 seconds, which is slower than the 3 minutes on the box. The temperature hold works well: I set 80 degrees for green tea and it held within 2 degrees over a 30 minute window.\n\nThe lid is the problem. After about six weeks the seal started to leak, and by September I was mopping the counter roughly once a week. Replacement seals are 12 GBP for a pack of three, which is fine, but they are not in the box.\n\nThree stars. If they fixed the lid it would be five."),
    # 15 trip report
    ("trip_report", "Trip report: Kagoshima, 8-14 September 2026\n\nPurpose: visit the Sendai plant and meet the QA team.\n\nMonday 8: arrived 21:40 local. Tuesday: plant tour with Hiroshi Tanabe, 09:00-12:30. The line runs 4,200 units a day across two shifts. Wednesday: QA review; we went through 310 defect records from the last 12 months and found 19 that were misclassified. Thursday: met the logistics team about the Rotterdam routing, which currently adds 6 days. Friday: wrap-up, departed 11:15.\n\nCost: 2,840 EUR including 1,120 EUR airfare. Main follow-up: a written proposal on the routing change, due to Hiroshi Tanabe by October 10."),
    # 16 proposal
    ("proposal", "Proposal: migrate the reporting database to a columnar store\n\nProblem. The reporting database holds 1.8 TB and answers most queries in 6 to 20 seconds. Analysts run about 400 queries a day, and 60 of those time out at the 30 second limit.\n\nProposal. Move the analytics replica to a columnar engine and keep the transactional store unchanged. Expected query times are 200 to 900 milliseconds for the same 400 queries. The change touches only the replica, so rollback is a replica rebuild.\n\nCost and schedule. Licensing is 18,000 USD a year. One engineer, six weeks, starting November 2. Dependencies: a snapshot pipeline, owned by Sofia Meier, and a change to the BI layer's connection string."),
    # 17 FAQ answer
    ("faq", "How long does a passport renewal take?\n\nRoutine service is 6 to 8 weeks from the day the application is received, not the day you post it. Expedited service is 2 to 3 weeks and costs an extra 60 USD.\n\nYou can apply by post or at one of 27 acceptance facilities. If you are travelling within 14 days you can request an appointment at a regional agency, but you must show proof of travel, such as a booking or an itinerary.\n\nApplications received after December 15 are not guaranteed to be processed before the holiday closure, which runs from December 24 to January 2."),
    # 18 changelog
    ("changelog", "Release 4.7.0 — November 4, 2026\n\nAdded\n- Native support for the Arrow IPC format in the reader.\n- A --dry-run flag for the migrate command.\n\nChanged\n- The default retry count is now 5, up from 3.\n- Error messages from the parser now include the column number as well as the line.\n\nFixed\n- A crash when reading files larger than 2 GB on 32-bit builds (issue 1189, reported by Ana Duarte on October 2).\n- The scheduler no longer drops the last job in a batch of 64 or more.\n\nBreaking: the config key pool_size is renamed worker_pool_size. The old key still works until 5.0 but prints a warning."),
    # 19 spec section
    ("spec", "### 4.2 Rate limiting\n\nClients are limited to 600 requests per minute per API key, measured over a sliding 60 second window. Requests above the limit receive HTTP 429 with a Retry-After header, in seconds.\n\nBursts: a client may exceed the limit by up to 20 percent for 10 seconds, provided its 60 second total stays under 600. The burst allowance is enforced by a token bucket with a capacity of 120 tokens and a refill rate of 10 tokens per second.\n\nLimits are per key, not per account. An account with four keys therefore gets 2,400 requests per minute in aggregate. Contact support if you need a higher ceiling; the standard contract allows up to 3,000."),
    # 20 announcement
    ("announcement", "We are retiring the legacy dashboard on March 31, 2027.\n\nEvery report in the legacy dashboard has an equivalent in the new console, with two exceptions: the 'Ad hoc pivot' tool and the scheduled CSV export. Both are on the roadmap for the first half of 2027 and both will be missing for at least two months.\n\nIf you rely on either, tell us before February 14 by replying to this message or writing to the data platform team. As of September 30 the legacy dashboard had 143 daily users, down from 610 in January. We will run both systems in parallel until March 31."),
]


def build_prompt(pf, draft):
    return pf["instr"] + "\n\n" + draft.strip() + pf["sep"]


def numbers(text):
    return {n.replace(",", "") for n in re.findall(r"\d[\d,\.]*%?", text)}


MONTHS = ("january february march april may june july august september october "
          "november december")
WEEKDAYS = ("monday tuesday wednesday thursday friday saturday sunday")
DATE_WORDS = re.compile(r"\b(%s|%s)\b" % (MONTHS.replace(" ", "|"),
                                          WEEKDAYS.replace(" ", "|")), re.I)
CAP_SEQ = re.compile(r"\b(?:[A-Z][a-z]+\s+){1,3}[A-Z][a-z]+\b")
MID_CAP = re.compile(r"(?<![.\n] )\b([A-Z][a-z]{2,})\b")

STOP = {"The", "This", "That", "There", "They", "Then", "These", "Those", "We",
        "You", "Your", "Our", "It", "Its", "If", "In", "On", "At", "By", "For",
        "From", "With", "And", "But", "Or", "So", "As", "Is", "Are", "Was",
        "Were", "Not", "No", "Do", "Does", "Did", "Can", "Will", "Would",
        "Should", "Must", "May", "Might", "All", "Any", "Some", "Each",
        "Every", "Both", "One", "Two", "Three", "Four", "Five", "Six", "Seven",
        "Eight", "Nine", "Ten", "Half", "Most", "More", "Other", "Out", "Over",
        "After", "Before", "When", "Where", "What", "Which", "Who", "Why",
        "How", "Here", "Now", "Just", "Only", "Also", "Still", "Even", "Much",
        "Many", "Very", "Same", "Two", "First", "Second", "Third", "Last",
        "Next", "Number", "Query", "Routing", "Home", "Since", "Round",
        "Routine", "Retention", "Report", "Review", "Warranty", "Cost",
        "Impact", "Duration", "Detected", "Resolved", "Timeline", "Root",
        "Breaking", "Added", "Changed", "Fixed", "Bursts", "Limits", "Clients",
        "Requests", "Applications", "Equipment", "Core", "Effective", "Remove",
        "Pull", "Fit", "Take", "Thread", "Grease", "Drive", "You", "Your",
        "Proposal", "Problem", "Remote", "Design", "Decisions", "Open",
        "Ports", "Available", "Dear", "Sincerely", "Attendees", "Date",
        "Purpose", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday",
        "Timeline", "Summary", "Incidents", "Actions", "Posted", "Release",
        "Native", "Every", "As", "Do", "What", "How", "We", "I", "It"}


def fact_tokens(text):
    nums = numbers(text)
    dates = {m.group(0).lower() for m in DATE_WORDS.finditer(text)}
    names = {m.group(0) for m in CAP_SEQ.finditer(text)}
    names |= {m.group(1) for m in MID_CAP.finditer(text)
              if m.group(1) not in STOP}
    return nums, dates, names


def fmt_counts(text):
    paras = [b for b in re.split(r"\n\s*\n", text.strip()) if b.strip()]
    bullets = len(re.findall(r"(?m)^\s*[-*] ", text))
    heads = len(re.findall(r"(?m)^#{1,6} ", text))
    return len(paras), bullets, heads


def call(url, model, prompt, max_tokens=2048, timeout=600):
    body = {
        "model": model,
        "prompt": prompt,
        "temperature": 1.0,
        "top_p": 0.95,
        "top_k": -1,          # vLLM: -1 disables top-k
        "min_p": 0.0,
        "repetition_penalty": 1.0,
        "max_tokens": max_tokens,
    }
    req = urllib.request.Request(url + "/v1/completions",
                                 json.dumps(body).encode("utf-8"),
                                 {"Content-Type": "application/json"})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=timeout) as r:
        payload = json.load(r)
    dt = time.time() - t0
    text = payload["choices"][0]["text"].strip()
    usage = payload.get("usage", {})
    return text, dt, usage


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:8000")
    ap.add_argument("--model", default="jialinyyzz/humanizer-GGUF")
    ap.add_argument("--samples", type=int, default=2)
    ap.add_argument("--out", default="results.json")
    args = ap.parse_args()

    prompt = build_prompt(PROMPT_FORMAT, "X")
    fp = hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:16]
    assert fp == PROMPT_FORMAT["fingerprint"], "prompt fingerprint mismatch: %s" % fp

    # endpoint sanity: /v1/models must advertise the served id
    with urllib.request.urlopen(args.url + "/v1/models", timeout=60) as r:
        served = [m["id"] for m in json.load(r)["data"]]
    print("served models:", served)

    rows = []
    tot_out_tokens = 0
    tot_seconds = 0.0
    for i, (genre, draft) in enumerate(DRAFTS, 1):
        d_nums, d_dates, d_names = fact_tokens(draft)
        d_paras, d_bul, d_head = fmt_counts(draft)
        for s in range(1, args.samples + 1):
            out, dt, usage = call(args.url, args.model,
                                  build_prompt(PROMPT_FORMAT, draft))
            o_nums, _, _ = fact_tokens(out)
            o_paras, o_bul, o_head = fmt_counts(out)
            low = out.lower()
            miss_nums = sorted(n for n in d_nums if n not in o_nums)
            miss_dates = sorted(d for d in d_dates if d not in low)
            miss_names = sorted(n for n in d_names
                                if n.lower() not in low)
            para_drop = max(0, d_paras - o_paras)
            bul_drop = max(0, d_bul - o_bul)
            head_drop = max(0, d_head - o_head)
            ct = usage.get("completion_tokens")
            tot_out_tokens += ct or 0
            tot_seconds += dt
            row = {
                "n": i, "genre": genre, "sample": s,
                "seconds": round(dt, 2),
                "prompt_tokens": usage.get("prompt_tokens"),
                "completion_tokens": ct,
                "missing_numbers": miss_nums,
                "missing_dates": miss_dates,
                "missing_names": miss_names,
                "fact_diff_count": len(miss_nums) + len(miss_dates) + len(miss_names),
                "paragraph_drop": para_drop,
                "bullet_drop": bul_drop,
                "heading_drop": head_drop,
                "formatting_drop_count": para_drop + bul_drop + head_drop,
                "output_words": len(out.split()),
                "output": out,
            }
            rows.append(row)
            print("[%02d/%d s%d] %-14s %5.1fs %4s tok  fact-diff %d  fmt-drop %d"
                  % (i, len(DRAFTS), s, genre, dt, ct, row["fact_diff_count"],
                     row["formatting_drop_count"]))

    n = len(rows)
    clean = sum(1 for r in rows if r["fact_diff_count"] == 0)
    fmt_clean = sum(1 for r in rows if r["formatting_drop_count"] == 0)
    summary = {
        "model": args.model,
        "url": args.url,
        "prompt_fingerprint": fp,
        "drafts": len(DRAFTS),
        "samples_per_draft": args.samples,
        "rewrites": n,
        "fact_clean_rewrites": clean,
        "fact_clean_rate": round(clean / n, 4),
        "fact_diff_total": sum(r["fact_diff_count"] for r in rows),
        "formatting_clean_rewrites": fmt_clean,
        "formatting_drop_total": sum(r["formatting_drop_count"] for r in rows),
        "total_completion_tokens": tot_out_tokens,
        "total_seconds": round(tot_seconds, 2),
        "wall_clock_s_per_1k_out_tokens": round(
            tot_seconds / (tot_out_tokens / 1000.0), 3) if tot_out_tokens else None,
        "mean_s_per_request": round(tot_seconds / n, 2),
        "mean_out_tokens_per_request": round(tot_out_tokens / n, 1),
        "config": {"temperature": 1.0, "top_p": 0.95, "top_k": -1,
                   "min_p": 0.0, "repetition_penalty": 1.0, "max_tokens": 2048,
                   "endpoint": "/v1/completions", "stop": None},
    }
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump({"summary": summary, "rewrites": rows}, f,
                  ensure_ascii=False, indent=1)
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()