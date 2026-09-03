#!/usr/bin/env python3
"""
Extract audio from a video and transcribe it with word-level timing using
faster-whisper. Writes:
  - <out_dir>/<stem>.segments.json  -- [{index, start, end, text}, ...]
  - <out_dir>/<stem>.<lang>.srt     -- source-language subtitles (sanity check)

This is the mechanical half of the translate-video skill: it only produces
a timestamped source-language transcript. Translation is a separate,
judgment-heavy step done by the agent directly on segments.json (see
SKILL.md) -- never bolted on here as a second model call.

Usage:
    python3 transcribe.py <video_path> [--out-dir DIR] [--model SIZE] [--language en]
"""
import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path


def extract_audio(video_path: Path, wav_path: Path) -> None:
    cmd = [
        "ffmpeg", "-y", "-i", str(video_path),
        "-vn", "-ac", "1", "-ar", "16000",
        "-f", "wav", str(wav_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg failed:\n{result.stderr[-2000:]}")


def format_timestamp(seconds: float) -> str:
    ms = round(seconds * 1000)
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def write_srt(segments: list, srt_path: Path) -> None:
    lines = []
    for seg in segments:
        lines.append(str(seg["index"]))
        lines.append(f"{format_timestamp(seg['start'])} --> {format_timestamp(seg['end'])}")
        lines.append(seg["text"])
        lines.append("")
    srt_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("video_path", type=Path)
    ap.add_argument("--out-dir", type=Path, default=None,
                     help="Defaults to the video's own directory.")
    ap.add_argument("--model", default="medium",
                     help="faster-whisper model size (tiny/base/small/medium/large-v3). "
                          "Bigger = more accurate, slower, bigger one-time download.")
    ap.add_argument("--language", default="en", help="Source language code.")
    args = ap.parse_args()

    video_path = args.video_path.resolve()
    if not video_path.exists():
        sys.exit(f"error: video not found: {video_path}")

    out_dir = (args.out_dir or video_path.parent).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = video_path.stem

    try:
        from faster_whisper import WhisperModel
    except ImportError:
        sys.exit(
            "error: faster-whisper is not installed.\n"
            "Run: pip install faster-whisper\n"
            "(the model itself downloads from huggingface.co on first use -- "
            "that must be reachable from this machine)."
        )

    with tempfile.TemporaryDirectory() as tmp:
        wav_path = Path(tmp) / "audio.wav"
        print(f"Extracting audio -> {wav_path}", file=sys.stderr)
        extract_audio(video_path, wav_path)

        print(f"Loading model '{args.model}' (first run downloads it)...", file=sys.stderr)
        model = WhisperModel(args.model, device="cpu", compute_type="int8")

        print("Transcribing...", file=sys.stderr)
        raw_segments, info = model.transcribe(
            str(wav_path), language=args.language, vad_filter=True,
        )

        segments = []
        for i, seg in enumerate(raw_segments, start=1):
            segments.append({
                "index": i,
                "start": seg.start,
                "end": seg.end,
                "text": seg.text.strip(),
            })

    if not segments:
        sys.exit("error: no speech detected -- check the video has an audio track with speech.")

    segments_path = out_dir / f"{stem}.segments.json"
    segments_path.write_text(json.dumps(segments, ensure_ascii=False, indent=2), encoding="utf-8")

    srt_path = out_dir / f"{stem}.{args.language}.srt"
    write_srt(segments, srt_path)

    print(f"Detected language: {info.language} (p={info.language_probability:.2f})", file=sys.stderr)
    print(f"Wrote {len(segments)} segments:", file=sys.stderr)
    print(f"  {segments_path}", file=sys.stderr)
    print(f"  {srt_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
