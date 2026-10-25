#!/usr/bin/env python3
"""Validate campaign copy, local evidence and assets; derive the review document.

X copy is deliberately ASCII, so twitter-text v3's non-URL weighted length is
one per character. Every http(s) URL counts as 23, independent of its length.
No external dependencies and no publishing capability.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import struct
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
URL = re.compile(r"https?://[^\s]+")


def x_length(text: str) -> int:
    assert text.isascii(), "X copy must remain ASCII for this exact weighted-count implementation"
    return len(URL.sub("", text)) + 23 * len(URL.findall(text))


def source_path(reference: str) -> Path:
    path = (HERE / reference).resolve()
    assert path.is_relative_to(ROOT), f"Source outside repository: {reference}"
    assert path.is_file(), f"Missing source: {reference}"
    return path


def png_size(path: Path) -> tuple[int, int]:
    header = path.read_bytes()[:24]
    assert header[:8] == b"\x89PNG\r\n\x1a\n", f"Not a PNG: {path.name}"
    assert header[12:16] == b"IHDR", f"Missing PNG dimensions: {path.name}"
    return struct.unpack(">II", header[16:24])


def render(data: dict) -> str:
    items = [item for beat in data["beats"] for item in beat["platform_items"].values()]
    scheduled_count = sum(item["scheduled"] for item in items)
    published_count = sum(item["published"] for item in items)
    lines = [
        "# CallStencil engineering campaign",
        "",
        "Derived from `campaign.json`; edit that canonical file and run `python3 campaign/validate.py --render`.",
        "",
        f"Prepared: {sum(item['prepared'] for item in items)}/{len(items)}. Scheduled: {scheduled_count}/{len(items)}. Published: {published_count}/{len(items)}.",
        f"Release claims: {data['release_claim_status']}. Ready for scheduling: {data['ready_for_scheduling']}.",
        "",
        data["status_note"],
        "",
        "All copy is English. Each beat's audience, hook, evidence, CTA, image and alt text apply to both platform items below. The X copy is adapted into threads rather than truncated from LinkedIn.",
        "",
        data["attribution"],
        "",
        "Posting order: problem → design tradeoff → reproducible demo → fair experiment → release quickstart. Per-platform schedule and publication metadata below reflect verified records only.",
        "",
    ]
    for beat in data["beats"]:
        lines += [
            f"## {beat['id']}: {beat['name']}", "",
            f"Audience: {beat['audience']}", "",
            f"Hook: {beat['hook']}", "",
            f"Evidence: {', '.join('`' + x + '`' for x in beat['evidence_references'])}", "",
            f"CTA: {beat['cta']}", "",
            f"Image: `{beat['image']}` ({beat['image_kind']}).", "",
            f"Alt text: {beat['alt_text']}", "",
            f"![{beat['alt_text']}]({beat['image']})", "",
            f"### LinkedIn — {len(beat['linkedin'])} characters", "",
            item_status(beat["platform_items"]["linkedin"]), "",
            beat["linkedin"], "",
            "### X thread", "",
            item_status(beat["platform_items"]["x"]), "",
        ]
        for index, post in enumerate(beat["x_thread"], 1):
            lines += [f"Post {index} — {x_length(post)} weighted characters", "", post, ""]
    return "\n".join(lines).rstrip() + "\n"


def item_status(item: dict) -> str:
    line = f"Item `{item['id']}`. Prepared: {item['prepared']}. Scheduled: {item['scheduled']}. Published: {item['published']}."
    if item["scheduled"]:
        record = item["schedule"]
        line += f" Account: {record['account']}; scheduled for {record['scheduled_for']} ({record['timezone']}); confirmation: `{record['evidence_path']}`."
    if item["published"]:
        record = item["publication"]
        line += f" Published at {record['published_at']}; URL: {record['url']}; readback: `{record['evidence_path']}`."
    return line


def check_item_state(item: dict) -> None:
    assert item["prepared"] is True
    assert isinstance(item["scheduled"], bool) and isinstance(item["published"], bool)
    if item["scheduled"]:
        record = item["schedule"]
        for key in ("account", "scheduled_for", "timezone", "evidence_path"):
            assert record[key].strip(), f"Missing schedule {key}: {item['id']}"
        assert datetime.fromisoformat(record["scheduled_for"]).utcoffset() is not None, "Schedule requires explicit UTC offset"
        source_path(record["evidence_path"])
    if item["published"]:
        record = item["publication"]
        assert datetime.fromisoformat(record["published_at"]).utcoffset() is not None
        assert record["url"].startswith("https://")
        source_path(record["evidence_path"])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--render", action="store_true", help="Regenerate CAMPAIGN.md from canonical JSON")
    parser.add_argument("--copy-only", action="store_true", help="Check copy and evidence before all assets arrive")
    parser.add_argument("--refresh-provenance", action="store_true", help="Record SHA-256 and dimensions for existing assets")
    parser.add_argument("--require-release", action="store_true", help="Require finalized public-release claims")
    args = parser.parse_args()
    data = json.loads((HERE / "campaign.json").read_text())
    provenance_path = HERE / "provenance.json"
    provenance = json.loads(provenance_path.read_text())
    assert data["language"] == "en"
    assert data["prepared"] is True
    assert len(data["beats"]) == 5
    assert len({b["id"] for b in data["beats"]}) == 5
    items = [item for beat in data["beats"] for item in beat["platform_items"].values()]
    assert data["scheduled"] == any(item["scheduled"] for item in items), "Top-level scheduled flag must reflect actual platform records"
    assert data["published"] == any(item["published"] for item in items), "Top-level published flag must reflect actual platform records"
    report = json.loads(source_path(data["evidence_snapshot"]["path"]).read_text())
    snapshot = data["evidence_snapshot"]
    for key in ("passed", "baseline_receipts", "guarded_receipts", "blocked_calls"):
        assert snapshot[key] == report[key], f"Evidence changed: {key}"
    assert report["passed"] is True
    assert snapshot["scenario_count"] == len(report["scenarios"]) == 11
    observations = [o for s in report["scenarios"] for o in s["observations"]]
    assert all(o["passed"] for o in observations)
    for mode, key in (("baseline", "baseline_receipts"), ("guarded", "guarded_receipts")):
        assert sum(o["receipt_delta"] for o in observations if o["mode"] == mode) == snapshot[key]
    paired = [s for s in report["scenarios"] if len(s["observations"]) == 2]
    assert len(paired) == 10
    assert sum(s["observations"][0]["receipt_delta"] == 1 and s["observations"][1]["receipt_delta"] == 0 for s in paired) == snapshot["blocked_calls"]
    assets = {a["path"]: a for a in provenance["assets"]}
    for beat in data["beats"]:
        assert 600 <= len(beat["linkedin"]) <= 1600, f"LinkedIn length: {beat['id']}"
        assert 3 <= len(beat["x_thread"]) <= 5, f"X thread length: {beat['id']}"
        assert all(0 < x_length(p) <= 280 for p in beat["x_thread"]), f"X post length: {beat['id']}"
        for field in ("audience", "hook", "cta", "alt_text", "image_kind"):
            assert beat[field].strip(), f"Missing {field}: {beat['id']}"
        assert len(beat["evidence_references"]) >= 1
        for reference in beat["evidence_references"]:
            source_path(reference)
        assert set(beat["platform_items"]) == {"linkedin", "x"}
        for platform in beat["platform_items"].values():
            check_item_state(platform)
        assert beat["image"] in assets, f"Missing provenance: {beat['image']}"
        asset = assets[beat["image"]]
        assert asset["kind"] == beat["image_kind"]
        for reference in asset.get("source_references", []):
            source_path(reference)
        if not args.copy_only:
            assert asset["inspection"]["status"] == "passed", f"Asset still needs visual inspection: {beat['image']}"
        image = HERE / beat["image"]
        if not args.copy_only or image.is_file():
            assert image.is_file() and image.stat().st_size > 100, f"Missing image: {image.name}"
            digest = hashlib.sha256(image.read_bytes()).hexdigest()
            dimensions = list(png_size(image))
            assert dimensions[0] >= 1000 and dimensions[1] >= 600, f"Image too small: {image.name}"
            if args.refresh_provenance:
                asset["sha256"] = digest
                asset["dimensions_px"] = dimensions
            else:
                assert asset.get("sha256") == digest, f"Asset changed: {image.name}; inspect then refresh provenance"
                assert asset.get("dimensions_px") == dimensions
    if args.refresh_provenance:
        provenance_path.write_text(json.dumps(provenance, indent=2) + "\n")
    expected = render(data)
    target = HERE / "CAMPAIGN.md"
    if args.render:
        target.write_text(expected)
    assert target.is_file() and target.read_text() == expected, "CAMPAIGN.md is stale; run with --render"
    if args.require_release:
        assert data["release_claim_status"] == "verified_public_release", "Release readback remains pending"
        assert data["ready_for_scheduling"] is True
        assert data.get("release_verification"), "Missing public release verification reference"
        verification = json.loads(source_path(data["release_verification"]["evidence_path"]).read_text())
        assert verification["anonymous_public_readback"] is True
        assert verification["all_assets_anonymously_downloaded_and_sha256_verified"] is True
        assert verification["release_url"] == data["release_url"]
        assert verification["immutable"] is True and verification["prerelease"] is True
        assert verification["tag"] == "v0.1.0"
        release = json.loads(source_path(data["release_verification"]["api_evidence_path"]).read_text())
        assert release["draft"] is False and release["immutable"] is True
        assert release["html_url"] == verification["release_url"]
        assert release["id"] == verification["release_id"]
        assert "callstencil-0.1.0-py3-none-any.whl" in verification["asset_names"]
        assert "SHA256SUMS" in verification["asset_names"]
    print("PASS: 5 LinkedIn posts (600–1600 chars), 5 X threads (3–5 posts, <=280 weighted chars), metadata and evidence." + (" Copy-only; missing assets were not required." if args.copy_only else " All 5 image files and provenance hashes verified."))
    print(f"Release status: {data['release_claim_status']}. Scheduled: {sum(item['scheduled'] for item in items)}/10. Published: {sum(item['published'] for item in items)}/10.")
    print("LinkedIn lengths: " + ", ".join(str(len(b["linkedin"])) for b in data["beats"]))
    print("X weighted lengths: " + "; ".join(",".join(str(x_length(p)) for p in b["x_thread"]) for b in data["beats"]))


if __name__ == "__main__":
    main()
