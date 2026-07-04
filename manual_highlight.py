"""수동 하이라이트 편집기 / Manual highlight builder.

이미 받아둔(로컬) 영상 파일과 사용자가 직접 입력한 하이라이트 시간대만으로
요약 영상을 만든다. 다운로드/오디오 에너지 분석 단계를 건너뛰고,
summarizer.py 의 검증된 cut_and_concat() 을 그대로 재사용한다.

시간대 입력 형식(한 줄에 하나):
    1:23 - 2:05
    83 - 125
    00:01:23,000 --> 00:02:05,000     (SRT 스타일도 허용)
구분자는 '-', '~', '->' , '-->' 모두 허용. 시각은 SS / MM:SS / HH:MM:SS.
"""
import argparse
import os
import re
import sys
import tempfile
from pathlib import Path
from typing import List, Tuple

from summarizer import (
    TRANSITION_STYLES,
    SFX_SPECS,
    GAME_PROMPT,
    cut_and_concat,
    extract_audio,
    transcribe,
    build_srt,
    get_duration,
    safe_filename,
)


def parse_time(token: str) -> float:
    """'1:23' / '01:02:03' / '83' / '83.5' / '00:01:23,500' -> 초(float)."""
    token = token.strip().replace(",", ".")
    if not token:
        raise ValueError("빈 시간 값")
    parts = token.split(":")
    parts = [float(p) for p in parts]
    if len(parts) == 1:
        return parts[0]
    if len(parts) == 2:
        return parts[0] * 60 + parts[1]
    if len(parts) == 3:
        return parts[0] * 3600 + parts[1] * 60 + parts[2]
    raise ValueError(f"시간 형식 오류: {token}")


_SEP_RE = re.compile(r"\s*(?:-->|->|~|-|–|—|to)\s*", re.IGNORECASE)


def parse_ranges(text: str) -> List[Tuple[float, float]]:
    """여러 줄의 시간대 텍스트를 (start, end) 리스트로 파싱."""
    ranges: List[Tuple[float, float]] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        # 콤마로 start,end 를 준 경우도 허용
        if _SEP_RE.search(line):
            a, b = _SEP_RE.split(line, maxsplit=1)
        elif "," in line and line.count(",") == 1:
            a, b = line.split(",", 1)
        else:
            raise ValueError(f"시작-끝 구분자를 찾을 수 없습니다: '{line}'")
        start = parse_time(a)
        end = parse_time(b)
        if end <= start:
            raise ValueError(f"끝 시간이 시작 시간보다 빨라요: '{line}'")
        ranges.append((start, end))
    return ranges


def main():
    parser = argparse.ArgumentParser(
        description="로컬 영상 + 수동 하이라이트 시간대 -> 요약 영상")
    parser.add_argument("video", help="로컬 영상 파일 경로")
    parser.add_argument("--ranges", default="",
                        help="하이라이트 시간대(여러 줄). 각 줄 'start - end'. "
                             "미지정 시 --ranges-file 사용")
    parser.add_argument("--ranges-file", default="",
                        help="하이라이트 시간대를 담은 텍스트 파일 경로")
    parser.add_argument("--output-dir", default="output", help="출력 폴더 (기본: output)")
    parser.add_argument("--name", default="",
                        help="출력 파일 이름(확장자 제외). 미지정 시 원본 파일명 사용")
    parser.add_argument("--transition-style", default="black",
                        choices=list(TRANSITION_STYLES.keys()),
                        help="화면 전환: none / black / white (기본 black)")
    parser.add_argument("--sfx", dest="sfx_kind", default="whoosh",
                        choices=list(SFX_SPECS.keys()),
                        help="전환 효과음 (기본 whoosh)")
    parser.add_argument("--no-transition", action="store_true",
                        help="화면 전환/효과음 모두 끄기")
    parser.add_argument("--subtitles", action="store_true",
                        help="완성 영상에서 자막(SRT) 자동 생성 (Whisper)")
    parser.add_argument("--model", default="small",
                        choices=["tiny", "base", "small", "medium", "large"],
                        help="Whisper 모델 (자막 켤 때만 사용, 기본 small)")
    parser.add_argument("--lang", default="ko", help="자막 언어 코드 (기본 ko)")
    parser.add_argument("--prompt", default=GAME_PROMPT,
                        help="Whisper initial_prompt (전문 용어 힌트)")
    args = parser.parse_args()

    if args.no_transition:
        args.transition_style = "none"
        args.sfx_kind = "none"

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
        print("ERROR: 하이라이트 시간대를 하나 이상 입력하세요.")
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
        print("ERROR: 유효한 하이라이트 구간이 없습니다.")
        sys.exit(1)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    base = args.name.strip() or os.path.splitext(os.path.basename(args.video))[0]
    safe = safe_filename(base)
    out_video = str(output_dir / f"{safe}_highlight.mp4")
    out_srt = str(output_dir / f"{safe}_highlight.srt")

    total = sum(e - s for s, e in segments)
    v_name = TRANSITION_STYLES.get(args.transition_style, args.transition_style)
    s_name = SFX_SPECS.get(args.sfx_kind, (None, None, 0, args.sfx_kind))[3]
    print(f"[1/{'3' if args.subtitles else '2'}] "
          f"{len(segments)}개 구간 컷 & 이어붙이기 "
          f"(총 {total:.1f}s / {total/60:.1f}분, 화면전환: {v_name} / 효과음: {s_name})")

    with tempfile.TemporaryDirectory(prefix="manual_hl_") as tmpdir:
        cut_and_concat(args.video, segments, out_video, tmpdir,
                       transition_style=args.transition_style,
                       sfx_kind=args.sfx_kind)

        if args.subtitles:
            print(f"[2/3] 완성 영상에서 오디오 추출...")
            wav_path = os.path.join(tmpdir, "audio.wav")
            extract_audio(out_video, wav_path)
            print(f"[3/3] Whisper 자막 생성 ({args.model})...")
            whisper_result = transcribe(wav_path, args.model, args.lang, args.prompt)
            out_dur = get_duration(out_video)
            srt_content = build_srt(whisper_result, [(0.0, out_dur)])
            with open(out_srt, "w", encoding="utf-8") as f:
                f.write(srt_content)

    print(f"\nDone!")
    print(f"  Video : {out_video}")
    if args.subtitles:
        print(f"  SRT   : {out_srt}")


if __name__ == "__main__":
    main()
