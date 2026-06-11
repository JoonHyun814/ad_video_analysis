#!/usr/bin/env bash
# 컷-씬 매핑 API curl 호출 예시
# 실행 전: cd ad_video_analysis && python -m mapping_pipeline.api

BASE_URL="http://localhost:8000"

# ─────────────────────────────────────────────
# 1. 서버 상태 확인
# ─────────────────────────────────────────────
curl -s "$BASE_URL/health" | python3 -m json.tool

# ─────────────────────────────────────────────
# 2. 기본 분석 — 시나리오 파일 업로드
# ─────────────────────────────────────────────
curl -s -X POST "$BASE_URL/analyze" \
  -F "video_file=@/path/to/ad.mp4" \
  -F "scenario_file=@/path/to/scenario.txt" \
  | python3 -m json.tool

# ─────────────────────────────────────────────
# 3. 기본 분석 — 시나리오 텍스트 직접 입력
# ─────────────────────────────────────────────
curl -s -X POST "$BASE_URL/analyze" \
  -F "video_file=@/path/to/ad.mp4" \
  -F "scenario_text=Scene 1: 제품 등장. 테이블 위 음료 캔 클로즈업.
Scene 2: 모델 등장. 음료를 마시며 미소 짓는다." \
  | python3 -m json.tool

# ─────────────────────────────────────────────
# 4. 파라미터 지정 — 컷 수·민감도·모델 조정
# ─────────────────────────────────────────────
curl -s -X POST "$BASE_URL/analyze" \
  -F "video_file=@/path/to/ad.mp4" \
  -F "scenario_file=@/path/to/scenario.txt" \
  -F "max_cuts=15" \
  -F "threshold=20.0" \
  -F "gemini_model=models/gemini-2.5-flash" \
  | python3 -m json.tool

# ─────────────────────────────────────────────
# 5. 결과를 파일로 저장
# ─────────────────────────────────────────────
curl -s -X POST "$BASE_URL/analyze" \
  -F "video_file=@/path/to/ad.mp4" \
  -F "scenario_file=@/path/to/scenario.txt" \
  -o result.json

# cut_analysis 와 cut_scene_mapping 만 추출 (jq 필요)
curl -s -X POST "$BASE_URL/analyze" \
  -F "video_file=@/path/to/ad.mp4" \
  -F "scenario_file=@/path/to/scenario.txt" \
  | jq '{cut_analysis: .cut_analysis, cut_scene_mapping: .cut_scene_mapping}'
