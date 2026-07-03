# 🎬 YouTube 요약기 & 영상 편집 도구

YouTube 영상을 자동으로 **요약**하고, **자막을 생성·편집**하며, 썸네일까지 합쳐 **완성 영상**을 만들어 주는 한국어 영상 제작 도구 모음입니다. Whisper 음성 인식과 ffmpeg를 기반으로 하며, 파이썬을 모르는 사람도 쓸 수 있는 **그래픽 UI(GUI)** 를 제공합니다.

> 게임 방송(디아블로2 등) 하이라이트 편집을 염두에 두고 만들었지만, 어떤 영상에도 사용할 수 있습니다.

---

## ✨ 주요 기능

이 도구는 세 가지 기능을 탭으로 묶은 GUI로 제공됩니다.

### 1. YouTube 요약기 (`summarizer.py`)
- YouTube URL만 넣으면 영상을 내려받아 **오디오 에너지가 높은 하이라이트 구간**을 자동으로 찾습니다.
- 목표 길이(예: 10분)에 맞춰 하이라이트를 골라 **요약 영상**을 만듭니다.
- Whisper로 **자막(SRT)** 을 자동 생성합니다.
- 서로 다른 하이라이트 사이에 **장면 전환 효과 + 효과음**을 넣을 수 있습니다.
- 결과물: `_summary.mp4`(요약 영상), `_summary.srt`(자막)

### 2. 완성 영상 만들기 (`finalize.py`)
- **영상 + 자막(SRT) + 썸네일** 3개를 골라 하나의 완성 mp4로 합칩니다.
- 자막을 화면에 **새겨넣기(하드섭)** → 어디서 재생해도 자막이 보입니다.
- 썸네일을 **① 인트로 클립**으로 앞에 붙이고, **② mp4 표지(커버 아트)** 로도 삽입합니다.
- 인트로 길이·자막 크기·각 옵션 on/off 조절 가능.

### 3. CapCut 자동 편집기 (`auto_editor.py`)
- **무음 구간 자동 컷** — 말이 없는 부분을 잘라 영상 템포를 살립니다.
- **버벅거림(반복 단어·필러) 자동 컷**.
- Whisper 기반 **자막 자동 생성**.
- [pycapcut](https://pypi.org/project/pycapcut/)으로 **CapCut 드래프트(초안) 파일**을 만들어, CapCut에서 이어서 편집할 수 있습니다.

---

## 🖥️ 화면 구성

| GUI | 파일 | 탭 |
|-----|------|----|
| 통합 도구 | `gui.py` | CapCut 자동 편집기 · YouTube 요약기 · 완성 영상 만들기 |
| 요약기 단독판 | `요약기_gui.py` | 영상 요약 · 완성 영상 만들기 |

---

## 📦 설치

### 준비물
- **Python 3.9+**
- **ffmpeg** (PATH에 등록되어 있거나, 스크립트 폴더 옆 `ffmpeg/bin/ffmpeg.exe` 로 배치)

### 파이썬 패키지 설치
```bash
pip install -r requirements.txt
```

`requirements.txt`
```
pycapcut>=0.0.3
openai-whisper
pydub
numpy
yt-dlp
```

---

## 🚀 사용법

### GUI로 실행 (추천)
```bash
python gui.py          # 통합 도구 (3개 탭)
python 요약기_gui.py    # 요약기 단독판 (2개 탭)
```
Windows에서는 함께 들어있는 `실행.bat` 을 더블클릭해도 됩니다.

### 명령줄(CLI)로 실행

**YouTube 요약**
```bash
python summarizer.py "https://youtu.be/XXXX" --target-min 10 --model small --lang ko
```
주요 옵션: `--target-min`(목표 분) · `--model`(tiny/base/small/medium/large) · `--expand-before`/`--expand-after`(하이라이트 앞뒤 확장 초) · `--max-height`(화질) · `--bridge-gap`(같은 장면 묶기 기준 초) · `--no-transition`(전환 효과 끄기)

**완성 영상 만들기**
```bash
python finalize.py 영상.mp4 자막.srt 썸네일.jpg -o 완성.mp4 --intro-sec 2.5 --font-size 24
```
옵션: `--no-intro`(인트로 생략) · `--no-cover`(표지 생략) · `--no-subs`(자막 새겨넣기 생략) · `--font`(자막 글꼴)

**CapCut 자동 편집**
```bash
python auto_editor.py 영상.mp4 CapCut초안폴더 --model base --lang ko
```
옵션: `--silence-db`(무음 판정 dB) · `--min-silence-ms`(최소 무음 길이) · `--padding-ms`(컷 여백) · `--no-stutter`(버벅임 컷 끄기)

---

## 🧠 동작 원리 (간단 정리)

- **하이라이트 탐지**: 오디오를 분석해 음량(에너지)이 높은 구간을 점수화하고, 목표 길이에 맞게 상위 구간을 선택합니다. 가까운 구간(`--bridge-gap` 이내)은 한 장면으로 이어붙입니다.
- **자막 생성**: OpenAI Whisper로 음성을 인식해 SRT를 만듭니다. 게임 용어 정확도를 위해 `initial_prompt` 로 도메인 단어를 힌트로 줍니다.
- **무손실 이어붙이기**: 인트로·본편을 동일 규격의 MPEG-TS 조각으로 인코딩한 뒤 `concat` 디먹서로 합쳐, 재인코딩 없이 정확한 길이로 결합합니다.
- **콘솔 창 숨김**: Windows에서 ffmpeg/yt-dlp 하위 프로세스가 검은 창을 띄우지 않도록 `CREATE_NO_WINDOW` + `-nostdin` 을 적용했습니다.

---

## 📁 저장소 구성

```
├── gui.py            # 통합 GUI (3개 탭)
├── 요약기_gui.py      # 요약기 단독 GUI (2개 탭)
├── summarizer.py     # YouTube 요약 엔진
├── finalize.py       # 영상+자막+썸네일 합치기
├── auto_editor.py    # CapCut 자동 편집 + 자막
├── 무설치_빌드.py      # 포터블(무설치) 배포본 빌드 스크립트
├── requirements.txt
├── 실행.bat           # Windows 실행 런처
├── LICENSE
└── README.md
```

> 참고: `배포/`, `배포_무설치/`, `배포_요약기_무설치/` 같은 **무설치 배포 번들(각 ~1.8GB, Python·ffmpeg·모델 포함)** 은 용량이 커서 저장소에 포함하지 않습니다(`.gitignore` 처리). 배포본은 `무설치_빌드.py` 로 생성합니다.

---

## 📝 라이선스

[MIT License](LICENSE) © 2026 Seung Kyu Hwang
