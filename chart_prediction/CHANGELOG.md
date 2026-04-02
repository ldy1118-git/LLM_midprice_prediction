# Chart-based Midprice Prediction - 변경 이력

## v1 (초기 버전)
- **프롬프트**: `prompts/A_v1.txt`
- **차트 코드 변경점**:
  - 전체 차트 너비에 걸친 빨간 수평 점선 (`axhline`) + 빨간 점 + 가격 라벨
  - 마지막 종가 위치에 colored box 표시
- **결과**: `output/gemini/flash/A_v1/`
- **문제점**:
  - Gemini가 빈 영역에 캔들을 그리지 못하고, 입력 차트를 저해상도로 그대로 복제
  - 전체 차트에 걸친 점선이 Gemini의 이미지 생성을 혼란시킬 가능성

---

## v2 (2025-03-25)
- **프롬프트**: `prompts/A.txt` (= 현재 버전)
- **차트 코드 변경점**:
  - `axhline` (전체 너비 점선) 제거 → 예측 영역(split~끝)에만 짧은 빨간 점선으로 변경
  - "colored box" 관련 코드/프롬프트 항목 삭제
  - 프롬프트에서 KEY MARKERS 간소화 (RED DOT + RED DASHED line in blank area만 유지)
- **결과**: `output/gemini/flash/A_v2/` (테스트 예정)
- **기대 효과**: 점선을 빈 영역에만 표시하여 Gemini가 예측 영역을 더 명확히 인식하도록 유도
