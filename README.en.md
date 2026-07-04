<div align="center">

[한국어](README.md) · **English**

<img src="assets/hero.en.svg" alt="Turn live streams into highlight videos" width="100%">

# 🔥 Live Highlight Maker (Portable)

**A video tool that automatically analyzes long live-stream VODs, extracts only the best moments (highlights),**
**and layers on subtitles, transitions and background music to produce an upload-ready finished video.**

Powered by Whisper speech recognition and ffmpeg · comes with a **graphical UI (GUI)** so you don't need to know Python

</div>

---

## 🎯 What is this?

Rewatching and editing an hours-long live stream from scratch is exhausting. This tool automates that process.

> **Just paste a VOD URL → it finds the hottest moments (highlights) on its own → cuts them into a short summary video at your target length → and even adds subtitles.**

It was built with game-stream highlight editing in mind, but works just as well on any live stream or video.

---

## ✨ Key features

The GUI (`요약기_gui.py`) has three tabs. A **KO/EN language toggle button (🌐)** sits in the top-right corner so you can switch the interface language anytime.

### 1️⃣ Summarize tab — turn a stream into highlights

- **Just paste the VOD URL** and it downloads the video, then automatically finds the **high audio-energy highlight segments**.
- Picks highlights to match your target length (e.g. 10 min) and builds a **summary video**.
- Auto-generates **subtitles (SRT)** with Whisper.
- Lets you add **screen transitions** (none / fade to black / white flash) and **transition SFX** (none / whoosh / swoosh / beep / pop / impact) between highlights.
- Set a **keep-original folder** and the downloaded source video is preserved instead of deleted → you can re-edit it later in the **Manual highlights tab**.
- Output: `title_summary.mp4` (summary video), `title_summary.srt` (subtitles)

### 2️⃣ Manual highlights tab — your video + your chosen ranges

- Build a summary video from a **local video file you already have** plus **highlight time ranges you type in yourself** — skipping the download and audio-analysis steps.
- Enter one range per line as `start - end`. `SS` / `MM:SS` / `HH:MM:SS` are all supported, e.g. `1:23 - 2:05`, `83 - 125`, `00:01:23,000 --> 00:02:05,000` (SRT style).
- Just like the Summarize tab, you can add **transitions / SFX**, and optionally auto-generate **subtitles (SRT)**.
- Output: `name_highlight.mp4`, `name_highlight.srt` (when subtitles are on)

### 3️⃣ Finalize tab — polish it for upload

- Combines your **summary video + subtitles (SRT) + thumbnail** into a single finished mp4.
- **Burns subtitles into** the picture (hardsub) → they show up on any player.
- Uses the thumbnail as an **① intro clip** at the front and also embeds it as **② the mp4 cover art**.
- Lets you attach a separate **intro / outro video** (a standalone mp4) before and after the main clip. Even with different resolution/aspect ratio, it's auto-converted to the main clip's spec and stitched in.
- Add **background music (BGM)** and it's automatically **looped (if short) or cut (if long)** to match the full length of the finished video. The volume is lowered (default 0.25) so it mixes under the original speech instead of covering it.
- Intro length, subtitle size, BGM volume, and each option can be toggled on/off.

---

## 💡 Recommended workflow

AI subtitles aren't perfect. Follow the order below to produce a **finished video with polished subtitles too**.

<div align="center">
<img src="assets/workflow.en.svg" alt="Recommended workflow: STEP 1 summarize → STEP 2 edit subtitles → STEP 3 finalize" width="100%">
</div>

```
① Summarize tab  →  auto-creates summary video (.mp4) + subtitle file (.srt)
        ↓
② Open the .srt in a text editor and fix wrong words/phrases by hand
        ↓
③ Finalize tab  →  combine the edited .srt + thumbnail + summary video. Done!
```

> **Tip:** Open the SRT file with Notepad (or Notepad++). Just fix the subtitle text and save. You don't need to touch the timecodes (the numbers).

---

## 🚀 3-minute quick start

1. **Double-click `실행.bat`** → the program window opens.
2. **`Summarize` tab** → paste the VOD URL → click **"Download & Summarize"** → the summary video (.mp4) and subtitles (.srt) are created automatically.
3. *(optional)* Open the **`.srt`** in a text editor, fix any wrong words, and save.
4. **`Finalize` tab** → select the video you just made + subtitles + thumbnail → click **"Make final video."**
5. The upload-ready **final mp4** is saved. Done! 🎉

---

## 📋 Detailed guide (on-screen)

### STEP 1 — Summarize tab

Below is the actual program screen. Just follow the numbers.

<div align="center">
<img src="assets/ui-summarize.en.svg" alt="Summarize tab guide — the role of each button and field" width="100%">
</div>

| Item | Description | Default |
|------|------|--------|
| Stream / video URL | Paste the VOD address to summarize | — |
| Output folder | Where the result files are saved | `output` |
| Target length (min) | Desired length of the summary | `10` min |
| Whisper model | Subtitle accuracy (bigger = more accurate, slower) | `small` recommended |
| Language | Spoken language | `ko` (Korean) |
| Quality | 360 / 480 / **720** / 1080 | `720` recommended |
| Pre-peak extend (s) | Extra time added before each highlight start | `5` s |
| Post-peak extend (s) | Extra time added after each highlight end | `20` s |
| Scene merge (s) | Segments closer than this are stitched smoothly | `8` s |
| Transition | Between highlights: none / fade to black / white flash | `fade to black` |
| Transition SFX | SFX at the transition: none / whoosh / swoosh / beep / pop / impact | `whoosh` |

**Button: click "Download & Summarize"** → download → analyze → edit, all automatic.
When finished, two files appear in the output folder:
- `title_summary.mp4` — summary video
- `title_summary.srt` — subtitle file

> The medium / large models are downloaded automatically over the internet on first use and stored in the `models` folder.

---

### STEP 2 — Edit the subtitle file (.srt) (optional, highly recommended)

Auto-generated subtitles sometimes mishear game-specific terms, names, etc. Reviewing and fixing them before finalizing makes for a much more polished video.

1. In the `output` folder, **open `title_summary.srt` in a text editor**.
2. Fix wrong words or awkward sentences and save (`Ctrl+S`).
3. SRT format example:
   ```
   1
   00:00:03,200 --> 00:00:06,800
   Hello everyone, starting the Diablo 2 walkthrough.

   2
   00:00:07,100 --> 00:00:10,400
   Today I'll clear the Baal waves quickly.
   ```
   → Leave the numbers and timecodes as-is; **edit only the text lines**.

---

### STEP 3 — Finalize tab

Combine the summary video + (edited) subtitles + thumbnail image into an upload-ready final mp4.

<div align="center">
<img src="assets/ui-finalize.en.svg" alt="Finalize tab guide — the role of each button and field" width="100%">
</div>

| Item | Description |
|------|------|
| Video file | Select the `_summary.mp4` made in STEP 1 |
| Subtitle file (SRT) | Select the `.srt` edited in STEP 2 (or the original if unedited) |
| Thumbnail image | Select a `.jpg` / `.png` image (e.g. your YouTube thumbnail) |
| Intro video (optional) | A separate clip to prepend to the main video (leave empty if none) |
| Outro video (optional) | A separate clip to append to the main video (leave empty if none) |
| Background music (optional) | A music file laid under the whole video (`.mp3`/`.m4a`/`.wav`, empty if none) |
| Output file | Where the final file is saved |
| Intro length (s) | How many seconds the thumbnail shows at the front (default `2.5`s) |
| Subtitle size | Font size of the burned-in subtitles (default `24`) |
| BGM volume | BGM level (0–1), relative to speech (default `0.25`) |
| Add intro | Use the thumbnail as the opening scene on/off |
| Insert cover | Embed the thumbnail as album-art-style cover in the mp4 on/off |
| Burn subtitles | Bake subtitles into the video (hardsub) on/off |

**Button: click "Make final video"** → everything is merged automatically and the final mp4 is saved.

---

## 📥 Installation

### A) Portable build (recommended — no Python needed)
Download the **portable zip (~1 GB)** that bundles Python, ffmpeg and the Whisper models, unzip it, and double-click `실행.bat` to run instantly.

> Get the portable zip from **[👉 GitHub Releases](../../releases)**.

### B) Run from source (for Python users)
```bash
pip install -r requirements.txt
python 요약기_gui.py        # or double-click 요약기_실행.bat
```

**Requirements**
- Python 3.9+
- ffmpeg (on your PATH, or placed at `ffmpeg/bin/ffmpeg.exe` next to the script folder)

---

## 🧠 How it works

- **Highlight detection**: analyzes the audio, scores segments with high loudness (energy), and picks the top ones to fit the target length. Nearby segments (within `--bridge-gap`) are stitched into one scene.
- **Subtitle generation**: transcribes speech with OpenAI Whisper to make the SRT. For game-term accuracy, `initial_prompt` feeds domain words as hints.
- **Lossless stitching**: encodes intro and main into MPEG-TS pieces of the same spec, then combines them with the `concat` demuxer — exact length, no re-encoding.
- **Background music insertion**: loops the BGM endlessly with `-stream_loop` to match the full finished-video length, then mixes it with the original audio (`amix`) and trims to the video length.
- **Hidden console windows**: on Windows, `CREATE_NO_WINDOW` + `-nostdin` keep ffmpeg/yt-dlp subprocesses from popping up black windows.

---

## 📁 Repository layout

```
├── 요약기_gui.py       # GUI (three tabs: Summarize · Manual highlights · Finalize)
├── summarizer.py       # stream-highlight summarization engine
├── manual_highlight.py # local video + manual time ranges → highlight video
├── finalize.py         # combine video + subtitles + thumbnail + BGM
├── 요약기_실행.bat    # Windows launcher (system Python)
├── 사용설명서.txt     # portable-build user manual (Korean)
├── assets/           # README images (banner · workflow · UI guides)
├── requirements.txt
├── LICENSE
└── README.md
```

> The portable bundle (~1.8 GB — includes Python, ffmpeg and Whisper models) and the zip are too large for the repo and are provided separately via [GitHub Releases](../../releases).

---

## 📝 License

[MIT License](LICENSE) © 2026 SKH
