import json
import os
import re
import signal
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import llm

model_name = "qwen3.5:4b"

system_prompt = '''
You are an expert political email analyzer tasked with identifying the specific campaign committee responsible for sending a given political fundraising email. Carefully examine the entire email text, paying special attention to:

1. The signature or sign-off section
2. The "Paid for by" disclaimer
3. Contact information and letterhead details

Your goal is to precisely identify the name of the political committee that funded and distributed the email. Look for explicit mentions of the committee name, such as "Caraveo for Congress", "OKGOP", or "Adam for Colorado". Return ONLY the exact name of the committee as it appears in the official disclaimer, not including the "Paid for by" preface.

If multiple committee names are present, choose the primary committee responsible for the email's creation and distribution. Be precise and avoid adding any additional commentary or explanation.

Respond with ONLY a JSON object in this exact format: {"committee": "<name>"}
'''

COMMITTEE_SCHEMA = {
    "type": "object",
    "properties": {
        "committee": {
            "type": "string",
            "description": "Name of the political committee from email disclaimers"
        }
    },
    "required": ["committee"]
}


def parse_llm_json(output: str) -> dict:
    output = output.strip()
    if output.startswith("{") and output.endswith("}"):
        return json.loads(output)

    match = re.search(r"\{.*\}", output, flags=re.DOTALL)
    if match:
        return json.loads(match.group(0))

    # Model returned a plain string instead of JSON — treat it as the committee name
    if output:
        return {"committee": output.strip("'\"")}

    raise json.JSONDecodeError("Expecting JSON object", output, 0)


_thread_local = threading.local()
_model_init_lock = threading.Lock()


def _get_thread_model():
    if not hasattr(_thread_local, "model"):
        with _model_init_lock:
            _thread_local.model = llm.get_model(model_name)
    return _thread_local.model


def process_email(email, raise_errors=False):
    model_obj = _get_thread_model()
    try:
        response = model_obj.prompt(
            email["body"],
            system=system_prompt,
            temperature=0,
            schema=COMMITTEE_SCHEMA,
            think=False,
        )
        raw = response.text()
        if raise_errors:
            print(f"[Debug] Raw response: {raw!r}", flush=True)
        parsed_response = parse_llm_json(raw)
        return email | parsed_response
    except json.JSONDecodeError:
        if raise_errors:
            raise
        print(f"[Error] Invalid JSON for: {email.get('subject', '')}")
        return email
    except Exception as e:
        if raise_errors:
            raise
        print(f"[Error] Email: {email.get('subject', '')} - {e}")
        return email


def updated_output_path(input_path: Path) -> Path:
    if input_path.suffix:
        return input_path.with_name(f"{input_path.stem}_updated{input_path.suffix}")
    return Path(f"{input_path}_updated")


def email_key(email: dict) -> tuple:
    return (
        email.get("email"),
        email.get("date"),
        email.get("subject"),
    )


def main(input_file: str, workers: int = 4, test: int = 0) -> None:
    input_path = Path(input_file)
    with open(input_path, "r") as f:
        emails = json.load(f)
    if test:
        emails = emails[:test]
        print(f"[Info] Test mode: processing first {test} emails", flush=True)
    print(f"[Info] Loaded {len(emails)} emails", flush=True)

    output_path = updated_output_path(input_path)
    existing_map = {}

    if output_path.exists():
        try:
            with open(output_path, "r") as f:
                existing = json.load(f)
            if isinstance(existing, list):
                existing_map = {email_key(item): item for item in existing if item.get("committee")}
        except json.JSONDecodeError:
            print("[Warning] Output file is not valid JSON. Starting fresh.")

    # Pre-fill results array preserving order; collect indices needing processing
    results = [None] * len(emails)
    to_process = []

    for i, email in enumerate(emails):
        if i == 0:
            print(
                f"[Info] First email keys={list(email.keys())} committee={email.get('committee')}",
                flush=True,
            )
        key = email_key(email)
        if key in existing_map:
            results[i] = existing_map[key]
        elif email.get("committee"):
            results[i] = email
        else:
            to_process.append(i)

    print(f"[Info] {len(to_process)} emails need processing ({len(emails) - len(to_process)} cached/skipped)", flush=True)
    print(f"[Info] Using {workers} parallel workers", flush=True)

    save_every = 200
    completed = 0
    lock = threading.Lock()       # protects results[] and completed
    save_lock = threading.Lock()  # serializes JSONL appends
    progress_path = output_path.with_suffix(".progress.jsonl")
    progress_file = open(progress_path, "a")

    # Recover results from a previous interrupted run's progress log
    if progress_path.exists():
        print("[Info] Recovering results from progress log...", flush=True)
        recovered = 0
        with open(progress_path) as f:
            for line in f:
                try:
                    entry = json.loads(line)
                    idx, result = entry["idx"], entry["result"]
                    if 0 <= idx < len(results) and results[idx] is None:
                        results[idx] = result
                        recovered += 1
                except (json.JSONDecodeError, KeyError, IndexError):
                    continue
        if recovered:
            to_process = [i for i in to_process if results[i] is None]
            print(f"[Info] Recovered {recovered} results, {len(to_process)} still need processing", flush=True)

    def _append_result(idx, result):
        """Append one result to JSONL progress file — fast, no full rewrite."""
        line = json.dumps({"idx": idx, "result": result})
        with save_lock:
            progress_file.write(line + "\n")
            progress_file.flush()

    def _full_save():
        """Write complete results to output JSON (slow, only at end/interrupt)."""
        on_main = threading.current_thread() is threading.main_thread()
        if on_main:
            old_handler = signal.signal(signal.SIGINT, signal.SIG_IGN)
        try:
            with lock:
                snapshot = [r for r in results if r is not None]
                progress = completed
            fd, tmp = tempfile.mkstemp(dir=output_path.parent, suffix=".tmp")
            try:
                with os.fdopen(fd, "w") as f:
                    json.dump(snapshot, f, indent=4)
                os.replace(tmp, output_path)
            except BaseException:
                try:
                    os.unlink(tmp)
                except OSError:
                    pass
                raise
            # Clear progress log since full save is current
            try:
                os.unlink(progress_path)
            except OSError:
                pass
            print(f"[Saved] {progress}/{len(to_process)} processed, {len(snapshot)} total", flush=True)
        finally:
            if on_main:
                signal.signal(signal.SIGINT, old_handler)

    def _process_and_store(idx):
        nonlocal completed
        email = emails[idx]
        print(email.get('subject'), flush=True)
        result = process_email(email, raise_errors=bool(test))
        with lock:
            results[idx] = result
            completed += 1
            c = completed
        _append_result(idx, result)
        if c % save_every == 0:
            print(f"[Progress] {c}/{len(to_process)} processed", flush=True)

    # Save on Ctrl+C before exiting
    shutdown_event = threading.Event()

    def _handle_sigint(sig, frame):
        print("\n[Interrupt] Saving full output...", flush=True)
        shutdown_event.set()
        _full_save()
        os._exit(0)

    prev_handler = signal.signal(signal.SIGINT, _handle_sigint)

    try:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {pool.submit(_process_and_store, idx): idx for idx in to_process}
            for future in as_completed(futures):
                if shutdown_event.is_set():
                    break
                try:
                    future.result()
                except Exception as e:
                    idx = futures[future]
                    print(f"[Error] Failed index {idx}: {e}", flush=True)
                    with lock:
                        results[idx] = emails[idx]
    finally:
        signal.signal(signal.SIGINT, prev_handler)
        progress_file.close()

    # Final full save
    _full_save()
    print(f"[Done] Saved to {output_path}", flush=True)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("input_file", help="Input JSON file")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--test", type=int, default=0, metavar="N",
                        help="Process only the first N emails")
    args = parser.parse_args()
    main(args.input_file, workers=args.workers, test=args.test)
