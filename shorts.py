"""쇼츠(9:16 세로 영상) 내보내기 / Shorts (vertical 9:16) exporter.

로컬 영상(또는 요약본)에서 지정한 구간을 잘라 세로 1080x1920 쇼츠용
영상으로 변환한다. 유튜브 Shorts / Instagram Reels / TikTok 규격.

- 세로 변환 방식:
    center : 화면 중앙을 9:16 으로 크롭 (게임 화면 등 중앙에 시선이 있을 때)
    blur   : 원본을 그대로 두고 위아래를 블러 배경으로 채움 (화면 전체가 중요할 때)
- 여러 구간을 주면 하드컷으로 이어붙인다 (쇼츠 특성상 전환 효과 없음).
- --subtitles 를 켜면 완성본에서 Whisper 로 자막을 뽑아 크게 새겨넣는다.

시간대 입력 형식은 manual_highlight.py 와 동일 (한 줄에 'start - end').
"""
import argparse
import os
import sys
import tempfile
from pathlib import Path

from summarizer import (
    GAME_PROMPT,
    cut_and_concat,
    extract_audio,
    transcribe,
    build_srt,
    get_duration,
    safe_filename,
)
from finalize import run_ffmpeg
from manual_highlight import parse_ranges

# 쇼츠 규격 (유튜브 Shorts / Reels / TikTok 공통)
SHORTS_W, SHORTS_H = 1080, 1920
SHORTS_MAX_SEC = 180  # 유튜브 Shorts 최대 3분

MODE_NAMES = {"center": "중앙 크롭", "blur": "블러 배경"}


def to_vertical(src: str, out_path: str, mode: str, srt_name: str = "",
                cwd: str = None, font: str = "Malgun Gothic",
                font_size: int = 20) -> None:
    """가로 영상을 1080x1920 세로로 변환하고, srt_name 이 있으면 자막도 새긴다.

    subtitles 필터 경로는 Windows 이스케이프가 까다로워 finalize 와 같은 방식으로
    SRT 를 작업 폴더(cwd)에 두고 상대 경로로 참조한다.
    """
    sub_filter = ""
    if srt_name:
        style = (f"FontName={font},FontSize={font_size},"
                 f"PrimaryColour=&H00FFFFFF,OutlineColour=&H90000000,"
                 f"BorderStyle=1,Outline=3,Shadow=1,MarginV=110,Alignment=2")
        sub_filter = f",subtitles={srt_name}:force_style='{style}'"

    if mode == "blur":
        # 배경: 화면을 꽉 채운 뒤 블러 / 전경: 원본 비율 그대로 가운데 배치
        fc = (f"[0:v]split[a][b];"
              f"[a]scale={SHORTS_W}:{SHORTS_H}:force_original_aspect_ratio=increase,"
              f"crop={SHORTS_W}:{SHORTS_H},boxblur=20:5[bg];"
              f"[b]scale={SHORTS_W}:-2[fg];"
              f"[bg][fg]overlay=(W-w)/2:(H-h)/2,setsar=1{sub_filter},format=yuv420p[v]")
    else:  # center
        fc = (f"[0:v]crop='min(iw,ih*{SHORTS_W}/{SHORTS_H})':ih,"
              f"scale={SHORTS_W}:{SHORTS_H},setsar=1{sub_filter},format=yuv420p[v]")

    cmd = ["ffmpeg", "-y", "-i", os.path.abspath(src),
           "-filter_complex", fc,
           "-map", "[v]", "-map", "0:a?",
           "-c:v", "libx264", "-preset", "fast", "-crf", "22",
           "-r", "30", "-fps_mode", "cfr",
           "-c:a", "aac", "-b:a", "128k", "-ar", "44100", "-ac", "2",
           "-movflags", "+faststart", os.path.abspath(out_path)]
    run_ffmpeg(cmd, label="(세로 변환)", cwd=cwd)


def main():
    parser = argparse.ArgumentParser(
        description="로컬 영상 + 구간 -> 쇼츠(9:16 세로) 영상")
    parser.add_argument("video", help="로컬 영상 파일 경로")
    parser.add_argument("--ranges", default="",
                        help="쇼츠로 만들 구간(여러 줄). 각 줄 'start - end'")
    parser.add_argument("--ranges-file", default="",
                        help="구간 목록을 담은 텍스트 파일 경로")
    parser.add_argument("--output-dir", default="output", help="출력 폴더 (기본: output)")
    parser.add_argument("--name", default="",
                        help="출력 파일 이름(확장자 제외). 미지정 시 원본 파일명 사용")
    parser.add_argument("--mode", default="center", choices=["center", "blur"],
                        help="세로 변환 방식: center(중앙 크롭) / blur(블러 배경). 기본 center")
    parser.add_argument("--subtitles", action="store_true",
                        help="완성 쇼츠에서 자막(SRT) 자동 생성 후 크게 새겨넣기")
    parser.add_argument("--model", default="small",
                        choices=["tiny", "base", "small", "medium", "large"],
                        help="Whisper 모델 (자막 켤 때만 사용, 기본 small)")
    parser.add_argument("--lang", default="ko", help="자막 언어 코드 (기본 ko)")
    parser.add_argument("--prompt", default=GAME_PROMPT,
                        help="Whisper initial_prompt (전문 용어 힌트)")
    parser.add_argument("--font", default="Malgun Gothic", help="자막 글꼴")
    parser.add_argument("--font-size", type=int, default=20,
                        help="자막 크기 (세로 화면 기준, 기본 20)")
    args = parser.parse_args()

    if not os.path.isfile(args.video):
        print(f"ERROR: 영상 파일을 찾을 수 없습니다: {args.video}")
        sys.exit(1)

    range_text = args.ranges
    if args.ranges_file:
        with open(args.ranges_file, "r", encoding="utf-8") as f:
            range_text = f.read()

    try:
        segments = parse_ranges(range_text)
    except ValueError as e:
        print(f"ERROR: 시간대 파싱 실패 - {e}")
        sys.exit(1)

    if not segments:
        print("ERROR: 쇼츠로 만들 구간을 하나 이상 입력하세요.")
        sys.exit(1)

    # 영상 길이를 벗어나는 구간은 잘라 맞춘다.
    try:
        dur = get_duration(args.video)
        clipped = []
        for s, e in segments:
            s = max(0.0, s)
            e = min(dur, e)
            if e - s >= 0.2:
                clipped.append((s, e))
            else:
                print(f"  (범위를 벗어나 건너뜀: {s:.1f}s ~ {e:.1f}s / 영상 {dur:.1f}s)")
        segments = clipped
    except Exception as e:
        print(f"  (영상 길이 확인 실패, 입력값 그대로 사용: {e})")

    if not segments:
        print("ERROR: 유효한 구간이 없습니다.")
        sys.exit(1)

    total = sum(e - s for s, e in segments)
    if total > SHORTS_MAX_SEC:
        print(f"  [주의] 총 길이 {total:.0f}초 - 유튜브 Shorts 최대는 {SHORTS_MAX_SEC}초(3분)입니다. "
              f"그대로 만들지만 Shorts 로는 올라가지 않을 수 있어요.")

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    base = args.name.strip() or os.path.splitext(os.path.basename(args.video))[0]
    safe = safe_filename(base)
    out_video = str(output_dir / f"{safe}_shorts.mp4")
    out_srt = str(output_dir / f"{safe}_shorts.srt")

    steps = 3 if args.subtitles else 2
    print(f"[1/{steps}] {len(segments)}개 구간 컷 & 이어붙이기 "
          f"(총 {total:.1f}s, 변환 방식: {MODE_NAMES[args.mode]})")

    with tempfile.TemporaryDirectory(prefix="shorts_") as tmpdir:
        # 1) 구간을 하드컷으로 이어붙인 가로 클립 (쇼츠는 전환 효과 없이 컷 편집이 기본)
        flat = os.path.join(tmpdir, "flat.mp4")
        cut_and_concat(args.video, segments, flat, tmpdir,
                       transition_style="none", sfx_kind="none")

        # 2) (선택) 자막 생성 — 이어붙인 짧은 클립에서 전사하므로 빠르다
        srt_name = ""
        if args.subtitles:
            print(f"[2/3] Whisper 자막 생성 ({args.model})...")
            wav_path = os.path.join(tmpdir, "audio.wav")
            extract_audio(flat, wav_path)
            whisper_result = transcribe(wav_path, args.model, args.lang, args.prompt)
            flat_dur = get_duration(flat)
            srt_content = build_srt(whisper_result, [(0.0, flat_dur)])
            if srt_content:
                srt_name = "subs.srt"
                with open(os.path.join(tmpdir, srt_name), "w", encoding="utf-8") as f:
                    f.write(srt_content)
                with open(out_srt, "w", encoding="utf-8") as f:
                    f.write(srt_content)
            else:
                print("  (인식된 자막이 없어 자막 없이 진행)")

        # 3) 세로 변환 + 자막 번인
        print(f"[{steps}/{steps}] 1080x1920 세로 변환...")
        to_vertical(flat, out_video, args.mode, srt_name=srt_name,
                    cwd=tmpdir, font=args.font, font_size=args.font_size)

    print(f"\nDone!")
    print(f"  Shorts : {out_video}")
    if args.subtitles and os.path.isfile(out_srt):
        print(f"  SRT    : {out_srt}")


if __name__ == "__main__":
    main()
