import argparse
import csv
import json
import string
import sys
from collections import Counter
from pathlib import Path
from statistics import mean, median

from rapidfuzz import fuzz

INVALID_COMMITTEES = {
    "", "none", "na", "n/a", "unknown", "not found", "not available",
    "no political committee identified", "cannot determine",
    "unable to determine",
}

PUNCT_TABLE = str.maketrans("", "", string.punctuation)

COMMITTEE_ALIASES = {
    "NRSC": "NATIONAL REPUBLICAN SENATORIAL COMMITTEE",
    "THE NATIONAL REPUBLICAN SENATORIAL COMMITTEE": "NATIONAL REPUBLICAN SENATORIAL COMMITTEE",
    "NRCC": "NATIONAL REPUBLICAN CONGRESSIONAL COMMITTEE",
    "THE NATIONAL REPUBLICAN CONGRESSIONAL COMMITTEE": "NATIONAL REPUBLICAN CONGRESSIONAL COMMITTEE",
    "VPP": "VOTER PROTECTION PROJECT",
    "THE VOTER PROTECTION PROJECT": "VOTER PROTECTION PROJECT",
    "VPP (WWW.PROTECTVOTING.ORG)": "VOTER PROTECTION PROJECT",
    "VPP (www.protectvoting.org)": "VOTER PROTECTION PROJECT",
    "DSCC": "DEMOCRATIC SENATORIAL CAMPAIGN COMMITTEE",
    "THE DEMOCRATIC SENATORIAL CAMPAIGN COMMITTEE": "DEMOCRATIC SENATORIAL CAMPAIGN COMMITTEE",
    "DCCC": "DEMOCRATIC CONGRESSIONAL CAMPAIGN COMMITTEE",
    "THE DEMOCRATIC CONGRESSIONAL CAMPAIGN COMMITTEE": "DEMOCRATIC CONGRESSIONAL CAMPAIGN COMMITTEE",
    "DNC": "DEMOCRATIC NATIONAL COMMITTEE",
    "THE DEMOCRATIC NATIONAL COMMITTEE": "DEMOCRATIC NATIONAL COMMITTEE",
    "THE DEMOCRATS": "DEMOCRATIC NATIONAL COMMITTEE",
    "HMP": "HOUSE MAJORITY PAC",
    "THE HOUSE MAJORITY PAC": "HOUSE MAJORITY PAC",
    "SMP": "SENATE MAJORITY PAC",
    "THE SENATE MAJORITY PAC": "SENATE MAJORITY PAC",
    "AB PAC": "AMERICAN BRIDGE 21ST CENTURY",
    "AMERICAN BRIDGE": "AMERICAN BRIDGE 21ST CENTURY",
    "AMERICAN BRIDGE PAC": "AMERICAN BRIDGE 21ST CENTURY",
    "NHGOP": "NEW HAMPSHIRE REPUBLICAN STATE COMMITTEE",
    "NH GOP": "NEW HAMPSHIRE REPUBLICAN STATE COMMITTEE",
    "NH REPUBLICAN PARTY": "NEW HAMPSHIRE REPUBLICAN STATE COMMITTEE",
    "REPUBLICAN PARTY OF NEW HAMPSHIRE": "NEW HAMPSHIRE REPUBLICAN STATE COMMITTEE",
    "MIGOP": "MICHIGAN REPUBLICAN PARTY",
    "MICHIGAN GOP": "MICHIGAN REPUBLICAN PARTY",
    "TRUMP SAVE AMERICA JFC": "TRUMP SAVE AMERICA JOINT FUNDRAISING COMMITTEE",
    "INDIANA GOP": "INDIANA REPUBLICAN STATE COMMITTEE",
    "DLCC PAC": "DEMOCRATIC LEGISLATIVE CAMPAIGN COMMITTEE",
    "ANDREW GILLUM, DEMOCRAT, FOR GOVERNOR": "ANDREW GILLUM FOR GOVERNOR",
    "THE ARIZONA DEMOCRATIC PARTY": "ARIZONA DEMOCRATIC PARTY",
    "ARIZONA DEMOCRATS": "ARIZONA DEMOCRATIC PARTY",
    "BECCA FOR VERMONT": "BECCA BALINT FOR VERMONT",
    "CAVPAC": "CHAMPION AMERICAN VALUES",
    "WISGOP": "REPUBLICAN PARTY OF WISCONSIN",
    "THE NEBRASKA REPUBLICAN PARTY": "NEBRASKA REPUBLICAN PARTY",
}


def _apply_aliases(value):
    return COMMITTEE_ALIASES.get(value, value)


def normalize_exact(value):
    if value is None:
        return None
    stripped = value.strip()
    if stripped.lower() in INVALID_COMMITTEES:
        return None
    cleaned = stripped.upper().translate(PUNCT_TABLE)
    cleaned = " ".join(cleaned.split())
    if not cleaned:
        return None
    return _apply_aliases(cleaned)


def normalize_fuzzy(value):
    if value is None:
        return None
    stripped = value.strip()
    if stripped.lower() in INVALID_COMMITTEES:
        return None
    cleaned = " ".join(stripped.upper().split())
    if not cleaned:
        return None
    return _apply_aliases(cleaned)


def email_key(rec):
    return (rec.get("email"), rec.get("date"), rec.get("subject"))


def load_committees(filepath, limit=None, disclaimer_only=False):
    print(f"  Loading {filepath}...", flush=True)
    with open(filepath) as f:
        records = json.load(f)
    if limit:
        records = records[:limit]
    result = {}
    for rec in records:
        if disclaimer_only and rec.get("disclaimer") != "True":
            continue
        result[email_key(rec)] = rec.get("committee")
    print(f"  -> {len(result):,} records", flush=True)
    return result


def bucket_score(score):
    if score == 100:
        return "100"
    if score >= 90:
        return "90-99"
    if score >= 80:
        return "80-89"
    if score >= 70:
        return "70-79"
    if score >= 50:
        return "50-69"
    return "<50"


def print_header(title):
    print(f"\n{'=' * 70}")
    print(f"  {title}")
    print(f"{'=' * 70}")


def print_section(title):
    print(f"\n{title}")
    print("-" * 70)


def main():
    parser = argparse.ArgumentParser(
        description="Compare committee extraction across LLM models"
    )
    parser.add_argument("--gemma", default="emails_updated_gemma4e4b.json")
    parser.add_argument("--qwen35", default="emails_updated_qwen35-4b.json")
    parser.add_argument("--qwen3", default="emails_updated_qwen3-4b.json")
    parser.add_argument("--export-json", type=Path, metavar="FILE")
    parser.add_argument("--export-csv", type=Path, metavar="FILE")
    parser.add_argument("--samples", type=int, default=50)
    parser.add_argument("--fuzzy-threshold", type=float, default=80.0)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--disclaimer", action="store_true",
                        help="Only include emails where disclaimer == 'True'")
    args = parser.parse_args()

    models = {
        "Gemma 4 E4B": args.gemma,
        "Qwen 3.5 4B": args.qwen35,
        "Qwen 3 4B": args.qwen3,
    }
    model_names = list(models.keys())
    pairs = [
        (model_names[0], model_names[1]),
        (model_names[0], model_names[2]),
        (model_names[1], model_names[2]),
    ]

    print("Loading files...")
    data = {}
    for name, path in models.items():
        data[name] = load_committees(path, args.limit, args.disclaimer)

    common_keys = set(data[model_names[0]].keys())
    for name in model_names[1:]:
        common_keys &= set(data[name].keys())

    all_keys = set()
    for name in model_names:
        all_keys |= set(data[name].keys())

    print_header("COMMITTEE EXTRACTION COMPARISON")

    print_section("KEY COVERAGE")
    for name in model_names:
        print(f"  {name + ' records:':<30} {len(data[name]):>10,}")
    print(f"  {'Common keys (intersection):':<30} {len(common_keys):>10,}")
    print(f"  {'All keys (union):':<30} {len(all_keys):>10,}")

    # NA distribution
    na_counts = {}
    for name in model_names:
        count = sum(
            1 for k in common_keys if normalize_exact(data[name][k]) is None
        )
        na_counts[name] = count

    print_section("NA VALUE DISTRIBUTION (over common keys)")
    for name in model_names:
        pct = 100 * na_counts[name] / len(common_keys) if common_keys else 0
        print(f"  {name + ' NA values:':<30} {na_counts[name]:>10,} ({pct:.1f}%)")

    all_na = sum(
        1 for k in common_keys
        if all(normalize_exact(data[n][k]) is None for n in model_names)
    )
    any_na = sum(
        1 for k in common_keys
        if any(normalize_exact(data[n][k]) is None for n in model_names)
    )
    print(f"  {'All three NA:':<30} {all_na:>10,}")
    print(f"  {'At least one NA:':<30} {any_na:>10,}")

    # Precompute normalized values
    exact_vals = {
        name: {k: normalize_exact(data[name][k]) for k in common_keys}
        for name in model_names
    }
    fuzzy_vals = {
        name: {k: normalize_fuzzy(data[name][k]) for k in common_keys}
        for name in model_names
    }

    # Exact matching
    three_way_exact = sum(
        1 for k in common_keys
        if exact_vals[model_names[0]][k] is not None
        and exact_vals[model_names[0]][k] == exact_vals[model_names[1]][k]
        == exact_vals[model_names[2]][k]
    )

    pairwise_exact = {}
    for a, b in pairs:
        count = sum(
            1 for k in common_keys
            if exact_vals[a][k] is not None
            and exact_vals[a][k] == exact_vals[b][k]
        )
        pairwise_exact[(a, b)] = count

    non_na_common = len(common_keys) - any_na

    print_section("EXACT MATCH (normalized, excluding NA)")
    print(f"  {'All three agree:':<30} {three_way_exact:>10,} ({100 * three_way_exact / len(common_keys):.1f}% of all, {100 * three_way_exact / non_na_common:.1f}% of non-NA)")
    for a, b in pairs:
        c = pairwise_exact[(a, b)]
        print(f"  {a + ' == ' + b + ':':<40} {c:>10,} ({100 * c / len(common_keys):.1f}%)")

    # Fuzzy matching
    print_section("FUZZY MATCH DISTRIBUTION (non-NA pairs only)")
    fuzzy_scores = {}
    for a, b in pairs:
        scores = []
        for k in common_keys:
            va, vb = fuzzy_vals[a][k], fuzzy_vals[b][k]
            if va is not None and vb is not None:
                scores.append(fuzz.ratio(va, vb))
        fuzzy_scores[(a, b)] = scores

    for a, b in pairs:
        scores = fuzzy_scores[(a, b)]
        if not scores:
            print(f"  {a} vs {b}: no non-NA pairs")
            continue
        buckets = Counter(bucket_score(s) for s in scores)
        print(f"\n  {a} vs {b}  (n={len(scores):,})")
        print(f"    Mean: {mean(scores):.1f}  |  Median: {median(scores):.1f}")
        for label in ["100", "90-99", "80-89", "70-79", "50-69", "<50"]:
            c = buckets.get(label, 0)
            pct = 100 * c / len(scores)
            bar = "#" * int(pct / 2)
            print(f"    {label:>6}: {c:>8,} ({pct:5.1f}%) {bar}")

    # Above-threshold summary
    print_section(f"FUZZY MATCH SUMMARY (threshold >= {args.fuzzy_threshold})")
    for a, b in pairs:
        scores = fuzzy_scores[(a, b)]
        if not scores:
            continue
        above = sum(1 for s in scores if s >= args.fuzzy_threshold)
        print(f"  {a + ' vs ' + b + ':':<40} {above:>10,} / {len(scores):,} ({100 * above / len(scores):.1f}%)")

    # Disagreement samples
    print_section(f"DISAGREEMENT SAMPLES (up to {args.samples})")
    all_disagree = []
    two_agree_one_diff = []
    near_miss = []
    complete_disagree = []

    for k in common_keys:
        ev = [exact_vals[n][k] for n in model_names]
        if any(v is None for v in ev):
            continue

        if ev[0] == ev[1] == ev[2]:
            continue

        raw = {n: data[n][k] for n in model_names}
        fv = {n: fuzzy_vals[n][k] for n in model_names}
        pair_fuzzy = {}
        for a, b in pairs:
            if fv[a] and fv[b]:
                pair_fuzzy[(a, b)] = fuzz.ratio(fv[a], fv[b])
            else:
                pair_fuzzy[(a, b)] = 0.0

        sample = {
            "key": {"email": k[0], "date": k[1], "subject": k[2][:80]},
            "values": {n: raw[n] for n in model_names},
            "fuzzy_scores": {f"{a} vs {b}": round(s, 1) for (a, b), s in pair_fuzzy.items()},
        }

        matches = sum(1 for a, b in pairs if ev[model_names.index(a)] == ev[model_names.index(b)])

        if matches == 0:
            min_fuzzy = min(pair_fuzzy.values())
            max_fuzzy = max(pair_fuzzy.values())
            if 70 <= max_fuzzy < 90:
                near_miss.append(sample)
            elif max_fuzzy < 50:
                complete_disagree.append(sample)
            else:
                all_disagree.append(sample)
        else:
            two_agree_one_diff.append(sample)

    samples = []
    categories = [
        ("ALL THREE DISAGREE", all_disagree),
        ("TWO AGREE, ONE DIFFERS", two_agree_one_diff),
        ("NEAR MISS (fuzzy 70-90)", near_miss),
        ("COMPLETE DISAGREEMENT (fuzzy <50)", complete_disagree),
    ]
    per_cat = max(1, args.samples // len(categories))
    for cat_name, cat_list in categories:
        selected = cat_list[:per_cat]
        for s in selected:
            s["category"] = cat_name
        samples.extend(selected)

    for s in samples[:args.samples]:
        print(f"\n  [{s['category']}]")
        print(f"  Email: {s['key']['email']}")
        print(f"  Subject: {s['key']['subject']}")
        for name in model_names:
            print(f"    {name + ':':<16} {s['values'][name]}")
        for pair_label, score in s["fuzzy_scores"].items():
            print(f"    Fuzzy {pair_label}: {score}")

    # Exports
    if args.export_json:
        stats = {
            "key_coverage": {
                "per_model": {n: len(data[n]) for n in model_names},
                "common_keys": len(common_keys),
                "all_keys": len(all_keys),
            },
            "na_distribution": {
                "per_model": {n: na_counts[n] for n in model_names},
                "all_na": all_na,
                "any_na": any_na,
            },
            "exact_match": {
                "three_way": three_way_exact,
                "pairwise": {f"{a} vs {b}": c for (a, b), c in pairwise_exact.items()},
            },
            "fuzzy_match": {
                f"{a} vs {b}": {
                    "count": len(scores),
                    "mean": round(mean(scores), 1) if scores else None,
                    "median": round(median(scores), 1) if scores else None,
                    "buckets": dict(Counter(bucket_score(s) for s in scores)),
                }
                for (a, b), scores in fuzzy_scores.items()
            },
            "samples": samples[:args.samples],
        }
        args.export_json.write_text(json.dumps(stats, indent=2))
        print(f"\n  JSON exported to {args.export_json}")

    if args.export_csv:
        rows = []
        for k in common_keys:
            ev = [exact_vals[n][k] for n in model_names]
            if any(v is None for v in ev):
                continue
            if ev[0] == ev[1] == ev[2]:
                continue

            row = {
                "email": k[0],
                "date": k[1],
                "subject": k[2],
            }
            for n in model_names:
                row[f"{n}_committee"] = data[n][k]
            row["exact_all_match"] = ev[0] == ev[1] == ev[2]
            for a, b in pairs:
                fva, fvb = fuzzy_vals[a][k], fuzzy_vals[b][k]
                row[f"fuzzy_{a}_vs_{b}"] = (
                    round(fuzz.ratio(fva, fvb), 1)
                    if fva and fvb else None
                )
            rows.append(row)

        if rows:
            with open(args.export_csv, "w", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=rows[0].keys())
                writer.writeheader()
                writer.writerows(rows)
            print(f"  CSV exported to {args.export_csv} ({len(rows):,} disagreement rows)")

    print(f"\n{'=' * 70}")
    print("  Done.")
    print(f"{'=' * 70}\n")


if __name__ == "__main__":
    main()
