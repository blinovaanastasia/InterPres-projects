#!/usr/bin/env python3
"""
Turn a translated segments JSON file into a proper .srt file.

Takes the same [{index, start, end, text}, ...] shape that transcribe.py
produces -- after the agent has replaced each "text" with its translation,
keeping "start"/"end" untouched so the subtitles stay in sync with the video.

This is deliberately the only place that knows the SRT timestamp format
(HH:MM:SS,mmm) -- translation happens on plain JSON, formatting happens here.

Usage:
    python3 build_srt.py <segments.json> <output.srt>
"""
import json
import sys
from pathlib import Path


def format_timestamp(seconds: float) -> str:
    ms = round(seconds * 1000)
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def main() -> None:
    if len(sys.argv) != 3:
        sys.exit(f"usage: {sys.argv[0]} <segments.json> <output.srt>")

    segments_path = Path(sys.argv[1])
    out_path = Path(sys.argv[2])

    segments = json.loads(segments_path.read_text(encoding="utf-8"))
    if not segments:
        sys.exit("error: segments file is empty")

    missing_text = [s["index"] for s in segments if not s.get("text", "").strip()]
    if missing_text:
        sys.exit(f"error: segments with empty text (not translated?): {missing_text}")

    lines = []
    for seg in segments:
        lines.append(str(seg["index"]))
        lines.append(f"{format_timestamp(seg['start'])} --> {format_timestamp(seg['end'])}")
        lines.append(seg["text"])
        lines.append("")

    out_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {len(segments)} subtitle lines -> {out_path}")


if __name__ == "__main__":
    main()
