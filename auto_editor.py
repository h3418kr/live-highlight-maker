#!/usr/bin/env python3
"""
CapCut 자동 편집기
  - 무음 구간 자동 컷
  - 버벅거림(반복 단어·필러) 자동 컷
  - Whisper 기반 자막 자동 생성
  - pycapcut으로 CapCut 드래프트 파일 생성

사용법:
  python auto_editor.py <영상파일> <CapCut초안폴더> [옵션]
"""

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import List, Optional, Tuple

def _setup_bundled_paths():
    """포터블 배포용: 스크립트 폴더 옆의 ffmpeg/bin을 PATH에 추가."""
    base = os.path.dirname(os.path.abspath(__file__))
    for rel in (os.path.join("ffmpeg", "bin"), "ffmpeg"):
        p = os.path.join(base, rel)
        if os.path.isdir(p) and os.path.exists(os.path.join(p, "ffmpeg.exe")):
            os.environ["PATH"] = p + os.pathsep + os.environ.get("PATH", "")
            break


_setup_bundled_paths()

import whisper
from pydub import AudioSegment
from pydub.silence import detect_nonsilent

import pycapcut as cc
from pycapcut import trange

# ── 상수 ──────────────────────────────────────────────────────────────────────
US = 1          # 1 마이크로초
MS = 1_000      # 1 밀리초 = 1,000 마이크로초
SEC = 1_000_000 # 1초 = 1,000,000 마이크로초

# 제거할 필러 단어 (한국어 + 영어)
FILLER_WORDS = {
    "음", "어", "아", "그", "뭐", "에", "음음", "어어",
    "그니까", "그러니까", "뭐냐", "이제",
    "uh", "um", "ah", "er", "hmm",
}

# Windows CapCut 초안 폴더 기본 경로 후보
_CAPCUT_DRAFT_PATHS = [
    os.path.expandvars(r"%LOCALAPPDATA%\CapCut\User Data\Projects\com.lveditor.draft"),
    os.path.expandvars(r"%USERPROFILE%\Documents\CapCut\User Data\Projects\com.lveditor.draft"),
    os.path.expandvars(r"%APPDATA%\CapCut\User Data\Projects\com.lveditor.draft"),
]


def find_default_drafts_folder() -> Optional[str]:
    for p in _CAPCUT_DRAFT_PATHS:
        if os.path.isdir(p):
            return p
    return None


# ── 유틸리티 ──────────────────────────────────────────────────────────────────

def run(cmd: List[str], **kwargs) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(cmd, check=True, capture_output=True, text=True, **kwargs)
    except FileNotFoundError:
        sys.exit(f"[오류] 명령어를 찾을 수 없습니다: {cmd[0]}\n"
                 "ffmpeg/ffprobe가 설치되어 PATH에 있는지 확인하세요.")
    except subprocess.CalledProcessError as e:
        sys.exit(f"[오류] 명령 실패: {' '.join(cmd)}\n{e.stderr}")


def extract_audio(video_path: str, out_wav: str) -> None:
    """ffmpeg으로 16kHz mono WAV 추출"""
    run(["ffmpeg", "-y", "-i", video_path,
         "-vn", "-ar", "16000", "-ac", "1", "-f", "wav", out_wav])


def get_video_info(video_path: str) -> Tuple[int, int, float]:
    """(width, height, duration_sec) 반환"""
    r = run(["ffprobe", "-v", "quiet", "-print_format", "json",
             "-show_streams", "-show_format", video_path])
    data = json.loads(r.stdout)
    width, height, duration = 1920, 1080, 0.0
    for stream in data.get("streams", []):
        if stream.get("codec_type") == "video":
            width = stream.get("width", 1920)
            height = stream.get("height", 1080)
    duration = float(data.get("format", {}).get("duration", 0))
    return width, height, duration


def fmt_sec(ms: int) -> str:
    s = ms // 1000
    return f"{s // 60}분 {s % 60}초"


# ── 1단계: 무음 구간 검출 ────────────────────────────────────────────────────

def detect_nonsilent_sections(
    audio_path: str,
    silence_thresh_db: int,
    min_silence_ms: int,
    padding_ms: int,
    min_segment_ms: int,
) -> List[Tuple[int, int]]:
    """
    pydub으로 비무음 구간 검출.
    Returns: list of (start_ms, end_ms)
    """
    audio = AudioSegment.from_file(audio_path)
    total_ms = len(audio)

    nonsilent = detect_nonsilent(
        audio,
        min_silence_len=min_silence_ms,
        silence_thresh=silence_thresh_db,
        seek_step=10,
    )
    if not nonsilent:
        print("  [경고] 비무음 구간을 찾지 못했습니다. silence_thresh_db 값을 높여보세요.")
        return []

    # 패딩 추가 후 겹치는 구간 병합
    padded: List[Tuple[int, int]] = []
    for s, e in nonsilent:
        padded.append((max(0, s - padding_ms), min(total_ms, e + padding_ms)))

    merged: List[Tuple[int, int]] = [padded[0]]
    for s, e in padded[1:]:
        if s <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], e))
        else:
            merged.append((s, e))

    return [(s, e) for s, e in merged if (e - s) >= min_segment_ms]


# ── 2단계: 버벅거림(반복 단어·필러) 구간 검출 ──────────────────────────────

def detect_stutter_ranges(whisper_result: dict) -> List[Tuple[int, int]]:
    """
    Whisper 단어 타임스탬프로 버벅거림 구간(ms) 검출.
    - 연속 반복 단어: "나나나는" 같은 반복 → 마지막 1개만 남김
    - 필러 단어: 음, 어, uh, um 등
    """
    ranges: List[Tuple[int, int]] = []

    for segment in whisper_result.get("segments", []):
        words = segment.get("words", [])
        if not words:
            continue

        i = 0
        while i < len(words):
            raw = words[i]["word"].strip()
            clean = raw.lower().strip(".,!?…-")

            # 필러 단어
            if clean in FILLER_WORDS:
                s = int(words[i]["start"] * 1000)
                e = int(words[i]["end"] * 1000)
                if e > s:
                    ranges.append((s, e))
                i += 1
                continue

            # 연속 반복 단어 탐지
            j = i + 1
            while j < len(words):
                nc = words[j]["word"].strip().lower().strip(".,!?…-")
                if nc == clean:
                    j += 1
                else:
                    break

            if j - i >= 2:
                # 앞쪽 반복들을 제거 (마지막 단어는 남김)
                s = int(words[i]["start"] * 1000)
                e = int(words[j - 1]["start"] * 1000)
                if e > s:
                    ranges.append((s, e))
            i = j

    return ranges


def subtract_ranges(
    keep: List[Tuple[int, int]],
    remove: List[Tuple[int, int]],
    min_segment_ms: int,
) -> List[Tuple[int, int]]:
    """keep 구간에서 remove 구간을 빼고 결과를 반환"""
    result = list(keep)
    for rm_s, rm_e in remove:
        next_result: List[Tuple[int, int]] = []
        for seg_s, seg_e in result:
            if rm_e <= seg_s or rm_s >= seg_e:
                next_result.append((seg_s, seg_e))
            else:
                if seg_s < rm_s:
                    next_result.append((seg_s, rm_s))
                if rm_e < seg_e:
                    next_result.append((rm_e, seg_e))
        result = next_result
    return [(s, e) for s, e in result if (e - s) >= min_segment_ms]


# ── 3단계: 자막 항목 생성 (타임라인 재매핑) ──────────────────────────────────

def build_subtitle_entries(
    whisper_result: dict,
    keep_sections_ms: List[Tuple[int, int]],
) -> List[Tuple[int, int, str]]:
    """
    원본 타임스탬프 → 편집된 타임라인으로 매핑.
    Returns: list of (start_us, duration_us, text)
    """
    # 각 keep 구간의 타임라인 시작 오프셋 계산
    mappings: List[Tuple[int, int, int]] = []  # (orig_s, orig_e, tl_offset_ms)
    tl_offset = 0
    for orig_s, orig_e in keep_sections_ms:
        mappings.append((orig_s, orig_e, tl_offset))
        tl_offset += orig_e - orig_s

    def orig_to_tl(t_ms: float) -> Optional[int]:
        for orig_s, orig_e, tl_s in mappings:
            if orig_s <= t_ms <= orig_e:
                return tl_s + int(t_ms - orig_s)
        return None

    entries: List[Tuple[int, int, str]] = []
    for seg in whisper_result.get("segments", []):
        text = seg["text"].strip()
        if not text:
            continue
        tl_s = orig_to_tl(seg["start"] * 1000)
        tl_e = orig_to_tl(seg["end"] * 1000)
        if tl_s is None or tl_e is None or tl_e <= tl_s:
            continue
        entries.append((tl_s * MS, (tl_e - tl_s) * MS, text))

    return entries


# ── 4단계: CapCut 드래프트 생성 ──────────────────────────────────────────────

def create_capcut_draft(
    video_path: str,
    keep_sections_ms: List[Tuple[int, int]],
    subtitle_entries: List[Tuple[int, int, str]],
    drafts_folder: str,
    draft_name: str,
    width: int,
    height: int,
    fps: int,
) -> None:
    folder = cc.DraftFolder(drafts_folder)
    script = folder.create_draft(draft_name, width, height, fps=fps, allow_replace=True)

    script.add_track(cc.TrackType.video, track_name="video")
    script.add_track(cc.TrackType.text, track_name="subtitles")

    # 비디오 세그먼트
    tl_us = 0
    for orig_s_ms, orig_e_ms in keep_sections_ms:
        src_start_us = orig_s_ms * MS
        dur_us = (orig_e_ms - orig_s_ms) * MS
        seg = cc.VideoSegment(
            video_path,
            trange(tl_us, dur_us),
            source_timerange=trange(src_start_us, dur_us),
        )
        script.add_segment(seg, "video")
        tl_us += dur_us

    # 자막 스타일
    subtitle_style = cc.TextStyle(
        size=7.0,
        bold=True,
        color=(1.0, 1.0, 1.0),
        align=1,              # 가운데 정렬
        auto_wrapping=True,
        max_line_width=0.82,
    )
    subtitle_border = cc.TextBorder(
        alpha=1.0,
        color=(0.0, 0.0, 0.0),
        width=30.0,
    )
    subtitle_clip = cc.ClipSettings(transform_y=-0.8)  # 하단 배치

    # 자막 세그먼트
    for start_us, dur_us, text in subtitle_entries:
        if dur_us <= 0:
            continue
        text_seg = cc.TextSegment(
            text,
            trange(start_us, dur_us),
            style=subtitle_style,
            clip_settings=subtitle_clip,
            border=subtitle_border,
        )
        script.add_segment(text_seg, "subtitles")

    script.save()


# ── 메인 ──────────────────────────────────────────────────────────────────────

def main() -> None:
    default_drafts = find_default_drafts_folder()

    parser = argparse.ArgumentParser(
        description="CapCut 자동 편집기 - 무음/버벅거림 컷 + 자막 자동 생성",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("video", help="편집할 영상 파일 경로")
    parser.add_argument(
        "drafts_folder",
        nargs="?",
        default=default_drafts,
        help="CapCut 초안 폴더 경로 (자동 감지 시도)",
    )
    parser.add_argument("--name", default=None,
                        help="드래프트 이름 (기본: 영상 파일명)")
    parser.add_argument("--model", default="base",
                        choices=["tiny", "base", "small", "medium", "large"],
                        help="Whisper 모델 크기 (클수록 정확하지만 느림)")
    parser.add_argument("--lang", default="ko",
                        help="영상 언어 코드 (ko=한국어, en=영어, ja=일본어 등)")
    parser.add_argument("--silence-db", type=int, default=-40,
                        help="무음 판단 기준 dB (높일수록 더 많이 잘림)")
    parser.add_argument("--min-silence-ms", type=int, default=400,
                        help="이 길이 이상의 무음만 제거 (ms)")
    parser.add_argument("--padding-ms", type=int, default=80,
                        help="컷 전후 여유 시간 (ms)")
    parser.add_argument("--min-segment-ms", type=int, default=200,
                        help="이 길이보다 짧은 세그먼트는 제거 (ms)")
    parser.add_argument("--fps", type=int, default=30,
                        help="출력 FPS")
    parser.add_argument("--no-stutter", action="store_true",
                        help="버벅거림 제거 비활성화 (무음 제거만 수행)")
    args = parser.parse_args()

    # ── 입력 검증 ──
    video_path = os.path.abspath(args.video)
    if not os.path.isfile(video_path):
        sys.exit(f"[오류] 영상 파일을 찾을 수 없습니다: {video_path}")

    if not args.drafts_folder:
        sys.exit(
            "[오류] CapCut 초안 폴더를 찾을 수 없습니다.\n"
            "직접 경로를 인수로 전달하세요:\n"
            '  python auto_editor.py video.mp4 "C:\\Users\\...\\com.lveditor.draft"'
        )
    drafts_folder = os.path.abspath(args.drafts_folder)
    if not os.path.isdir(drafts_folder):
        sys.exit(f"[오류] CapCut 초안 폴더가 없습니다: {drafts_folder}")

    draft_name = args.name or Path(video_path).stem

    print("=" * 60)
    print("  CapCut 자동 편집기")
    print("=" * 60)
    print(f"  영상       : {video_path}")
    print(f"  초안 폴더  : {drafts_folder}")
    print(f"  드래프트   : {draft_name}")
    print(f"  Whisper    : {args.model} / 언어={args.lang}")
    print(f"  무음 기준  : {args.silence_db} dB, {args.min_silence_ms}ms 이상")
    print(f"  버벅 제거  : {'비활성' if args.no_stutter else '활성'}")
    print("=" * 60)

    with tempfile.TemporaryDirectory() as tmpdir:
        wav_path = os.path.join(tmpdir, "audio.wav")

        # 1. 오디오 추출
        print("\n[1/4] 오디오 추출 중...")
        extract_audio(video_path, wav_path)
        width, height, duration_sec = get_video_info(video_path)
        total_ms = int(duration_sec * 1000)
        print(f"      해상도: {width}×{height}  |  길이: {duration_sec:.1f}초")

        # 2. Whisper 음성 인식
        print(f"\n[2/4] 음성 인식 중... (모델: {args.model})")
        print("      (처음 실행 시 모델 다운로드로 시간이 걸릴 수 있습니다)")
        _mroot = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models")
        model = whisper.load_model(
            args.model, download_root=_mroot if os.path.isdir(_mroot) else None)
        result = model.transcribe(
            wav_path,
            language=args.lang,
            word_timestamps=True,
            verbose=False,
        )
        n_words = sum(len(s.get("words", [])) for s in result.get("segments", []))
        n_segs = len(result.get("segments", []))
        print(f"      인식 완료: {n_words}개 단어 / {n_segs}개 문장")

        # 3. 무음 + 버벅거림 구간 검출
        print("\n[3/4] 구간 분석 중...")

        keep = detect_nonsilent_sections(
            wav_path,
            silence_thresh_db=args.silence_db,
            min_silence_ms=args.min_silence_ms,
            padding_ms=args.padding_ms,
            min_segment_ms=args.min_segment_ms,
        )
        silent_removed_ms = total_ms - sum(e - s for s, e in keep)
        print(f"  무음 제거  : {silent_removed_ms / 1000:.1f}초 제거됨")

        if not args.no_stutter:
            stutter_ranges = detect_stutter_ranges(result)
            keep = subtract_ranges(keep, stutter_ranges, args.min_segment_ms)
            stutter_removed_ms = (total_ms - silent_removed_ms) - sum(e - s for s, e in keep)
            print(f"  버벅 제거  : {stutter_removed_ms / 1000:.1f}초 제거됨 ({len(stutter_ranges)}개 구간)")

        kept_ms = sum(e - s for s, e in keep)
        removed_ms = total_ms - kept_ms
        ratio = removed_ms / total_ms * 100 if total_ms else 0
        print(f"  원본: {duration_sec:.1f}초  →  편집 후: {kept_ms/1000:.1f}초  (제거: {removed_ms/1000:.1f}초, {ratio:.1f}%)")

        if not keep:
            sys.exit("[오류] 남은 구간이 없습니다. silence_db 값을 높이거나 min_silence_ms를 늘려보세요.")

        # 자막 타임라인 재매핑
        subtitle_entries = build_subtitle_entries(result, keep)
        print(f"  자막       : {len(subtitle_entries)}개 항목")

        # 4. CapCut 드래프트 생성
        print(f"\n[4/4] CapCut 드래프트 생성 중...")
        create_capcut_draft(
            video_path=video_path,
            keep_sections_ms=keep,
            subtitle_entries=subtitle_entries,
            drafts_folder=drafts_folder,
            draft_name=draft_name,
            width=width,
            height=height,
            fps=args.fps,
        )

    print(f"\n✅ 완료!")
    print(f"   CapCut을 열고 '{draft_name}' 드래프트를 확인하세요.")
    print(f"   드래프트 위치: {os.path.join(drafts_folder, draft_name)}")


if __name__ == "__main__":
    main()
