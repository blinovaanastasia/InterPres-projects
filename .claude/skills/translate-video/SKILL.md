---
name: translate-video
description: Translate a video's speech from one language to another (default English to Russian). Produces translated .srt subtitles with the original timing, plus a plain-text running translation. Use when the user wants a video translated, dubbed-as-text, or subtitled into another language.
---

# Translate Video

Turns a video's speech into a timestamped translation. The pipeline has two
halves that must stay separate:

1. **Mechanical** (scripts, deterministic): extract audio, transcribe with
   timing, format the final `.srt`. Never done by hand, never skipped.
2. **Judgment** (you, the agent): translating each line. Never delegated to
   another model call — you're already here, and a second translation API
   would just add a dependency and a place for context to get lost.

## Prerequisites

```
apt-get install -y ffmpeg          # audio extraction
pip install faster-whisper         # local speech-to-text, CPU-friendly
```

`faster-whisper` downloads its model from huggingface.co the first time a
given model size is used (a few hundred MB, cached after that). **If this
environment's network policy blocks huggingface.co** (check with `curl -sS
"$HTTPS_PROXY/__agentproxy/status"` if one is configured, or just try
running step 1 below), transcription cannot happen inside this session.
In that case tell the user plainly and ask for a timestamped transcript
produced elsewhere (their own Whisper run, YouTube captions, etc.) in the
`segments.json` shape from Step 1 — the rest of the skill runs unchanged
from there.

## Step 1 — transcribe

```
python3 <skill_dir>/scripts/transcribe.py <video_path> --language en
```

Produces, next to the video (or in `--out-dir`):
- `<name>.segments.json` — `[{index, start, end, text}, ...]` in the source language
- `<name>.en.srt` — source-language subtitles (a sanity check — open it if the source audio is unclear, to confirm the transcript before translating)

Default model is `medium`. For a difficult recording (accents, jargon,
overlapping speech) rerun with `--model large-v3` — slower and a bigger
download, but noticeably more accurate. Don't reach for `large-v3` by
default; only step up when `medium` visibly mis-hears things.

## Step 2 — translate (you do this directly)

Read `<name>.segments.json`. For every segment, replace `text` with its
translation into the target language (default Russian) and write the file
back out — same file, same `index`/`start`/`end`, only `text` changes.

Rules for the translation itself:
- Translate for a natural spoken register, not a literal word-for-word
  crib — this is speech, not prose.
- A segment is a caption-timing unit, not a sentence. If a sentence spans
  two segments, translate the sentence as a whole for meaning, then split
  the result back across the same two segments at a natural break — don't
  force a translation to respect a boundary the source only has because of
  a pause.
- Keep names, numbers, and technical terms intact unless the user's
  domain vocabulary (e.g. a project's `CONTEXT.md`) says otherwise.
- If a stretch of audio is inaudible or ambiguous in the source `.srt`,
  say so in your reply rather than guessing silently — a wrong guess in a
  subtitle is worse than a flagged gap.

## Step 3 — build the deliverables

```
python3 <skill_dir>/scripts/build_srt.py <name>.segments.json <name>.ru.srt
```

This is purely mechanical (timestamp formatting) — never hand-format an
`.srt`, always go through this script so the timing can't drift from
Step 1's numbers.

Then also write `<name>.ru.txt`: the same translation as running prose,
segments merged into natural paragraphs (no indices or timestamps) — this
is what a reader opens when they just want the translated text, not a
subtitle file to load into a player.

## Delivering the result

Send both `<name>.ru.srt` and `<name>.ru.txt` to the user (`SendUserFile`).
Mention the source `.en.srt` if anything in the transcript looked
uncertain, so they can sanity-check that spot against the video.
