"""M5 — generation/AITIVE_스토리보드_틀.html(인물/제품/Environment/컷별 4개 섹션만 남긴
이미지 슬롯 중심 빈 틀)을 프로젝트별로 실제 등장인물 수·컷 수에 맞춰 채운 HTML로 찍어낸다.

빈 틀은 예시로 인물 2명·컷 8개를 하드코딩해 뒀지만, 실제 프로젝트마다 M4 cast[]/scenes[]
개수가 다르므로 이 파일이 그 자리를 대신 채운다. CSS와 마크업 구조는 빈 틀과 완전히 동일하게
유지한다(사용자가 확정한 디자인 — 텍스트는 슬롯당 캡션 하나뿐, 카메라/조명/기법/크레딧/
메타데이터 섹션 없음). 슬롯 캡션은 M4 cast[].id/scenes[].cut_index 를 그대로 써서
StoryboardShotPlan(schemas.py)의 characters[].id/cuts[].cut_index 와 곧바로 매칭되게 한다 —
storyboard_codex.py 가 이 캡션 문자열을 키로 이미지를 삽입한다.
"""
from __future__ import annotations

from typing import Any

_STYLE = """
  @import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.css');

  :root{
    --primary-700:#4c25d9; --primary-600:rgb(95,58,242); --primary-500:#7a5cf5;
    --primary-100:#ece7fe; --primary-50:#f5f2ff;
    --gray-900:#14151a; --gray-800:#1f2129; --gray-700:#33353f; --gray-600:#4b4e5a;
    --gray-500:#6b6e7b; --gray-400:#9498a5; --gray-300:#c7cad3; --gray-200:#e3e5ea;
    --gray-100:#f0f1f4; --gray-50:#f7f8fa; --white:#fff;
    --outline:inset 0 0 0 1px var(--gray-200);
    --shadow-md:0 2px 8px rgba(20,21,26,.08), 0 1px 3px rgba(20,21,26,.05);
    --font:"Pretendard","Pretendard Variable",Inter,-apple-system,system-ui,sans-serif;
  }
  *{box-sizing:border-box;margin:0;padding:0}
  body{font-family:var(--font);background:var(--gray-50);color:var(--gray-900);
       line-height:1.5;-webkit-font-smoothing:antialiased;letter-spacing:-.01em;padding:24px}

  .sheet{width:1800px;margin:0 auto;background:var(--white);border-radius:16px;overflow:hidden;
         box-shadow:var(--outline),var(--shadow-md)}

  .row{display:grid;border-bottom:1px solid var(--gray-200)}
  .row:last-child{border-bottom:none}
  .r1{grid-template-columns:1fr 1fr}
  .r2{grid-template-columns:minmax(0,0.8fr) minmax(0,2.2fr)}
  .cell{padding:18px 20px 20px;border-right:1px solid var(--gray-200)}
  .cell:last-child{border-right:none}

  .sec{display:flex;align-items:center;gap:9px;margin-bottom:12px}
  .sec .n{font-size:.66rem;font-weight:800;color:var(--white);background:var(--primary-600);
          border-radius:6px;padding:3px 8px;letter-spacing:.04em;line-height:1.2}
  .sec .kr{font-size:.95rem;font-weight:800;color:var(--gray-900);letter-spacing:-.01em}

  .repeat{border:1px dashed var(--gray-300);border-radius:10px;padding:12px;margin-bottom:10px}
  .repeat:last-child{margin-bottom:0}

  .g3{display:grid;grid-template-columns:repeat(3,1fr);gap:8px}
  .g4{display:grid;grid-template-columns:repeat(4,1fr);gap:8px}

  .slot{border:1.5px dashed var(--gray-300);border-radius:10px;background:var(--gray-50);
        display:flex;align-items:center;justify-content:center;text-align:center;
        padding:8px;min-height:140px}
  .slot.tall{min-height:220px}
  .slot.short{min-height:110px}
  .slot span{font-size:.62rem;font-weight:700;color:var(--gray-400);letter-spacing:.02em}

  .frames{display:grid;grid-template-columns:repeat(4,1fr);gap:10px}
  .frame{display:flex;flex-direction:column;gap:6px}
  .frame .fno{font-size:.6rem;font-weight:800;background:var(--primary-600);color:var(--white);
              width:18px;height:18px;border-radius:5px;display:flex;align-items:center;justify-content:center}

  @media print{
    body{background:#fff;padding:0}
    .sheet{width:100%;border-radius:0;box-shadow:none;border:1px solid var(--gray-300)}
  }
"""


def _character_block(cast_id: str) -> str:
    return f"""      <div class="repeat">
        <div class="g3">
          <div class="slot"><span>{cast_id} · 정면</span></div>
          <div class="slot"><span>{cast_id} · 측면</span></div>
          <div class="slot"><span>{cast_id} · 의상 착용</span></div>
        </div>
      </div>"""


def _cut_card(cut_index: int) -> str:
    return (f'        <div class="frame"><span class="fno">{cut_index}</span>'
            f'<div class="slot short"><span>컷{cut_index}</span></div></div>')


def render_storyboard_html(cast_ids: list[str], cut_count: int, *, doc_title: str = "스토리보드") -> str:
    """빈 틀(AITIVE_스토리보드_틀.html)과 동일한 CSS/마크업으로, 인물 슬롯을 cast_ids 개수만큼,
    컷 카드를 cut_count 개만큼 찍어낸 완성 HTML 문자열을 반환한다.

    cast_ids: M4 cast[].id 리스트(예: ["캐릭터1", "캐릭터2"]) — 슬롯 캡션에 그대로 쓰여
    StoryboardShotPlan.characters[].id 와 매칭된다.
    cut_count: M4 scenes[] 개수 — 컷 카드는 1..cut_count 로 번호가 매겨져
    StoryboardShotPlan.cuts[].cut_index 와 매칭된다.
    """
    if not cast_ids:
        raise ValueError("cast_ids가 비어 있음 — M4 scenario.cast 가 최소 1명은 있어야 한다")
    if cut_count < 1:
        raise ValueError("cut_count가 1 미만 — M4 scenario.scenes 가 최소 1개는 있어야 한다")

    character_blocks = "\n".join(_character_block(cid) for cid in cast_ids)
    cut_cards = "\n".join(_cut_card(i) for i in range(1, cut_count + 1))

    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{doc_title}</title>
<style>{_STYLE}</style>
</head>
<body>

<div class="sheet">

  <!-- ══ ROW 1 ══ -->
  <div class="row r1">

    <!-- 1. 인물 묘사 -->
    <div class="cell">
      <div class="sec"><span class="n">1.</span><span class="kr">인물 묘사</span></div>

{character_blocks}
    </div>

    <!-- 2. 제품 묘사 -->
    <div class="cell">
      <div class="sec"><span class="n">2.</span><span class="kr">제품 묘사</span></div>
      <div class="g4">
        <div class="slot"><span>제품 · 컷1</span></div>
        <div class="slot"><span>제품 · 컷2</span></div>
        <div class="slot"><span>제품 · 컷3</span></div>
        <div class="slot"><span>제품 · 로고</span></div>
      </div>
    </div>
  </div>

  <!-- ══ ROW 2 ══ -->
  <div class="row r2">

    <!-- 3. Environment 묘사 -->
    <div class="cell">
      <div class="sec"><span class="n">3.</span><span class="kr">Environment 묘사</span></div>
      <div class="slot tall"><span>Environment</span></div>
    </div>

    <!-- 4. 컷별 묘사 -->
    <div class="cell">
      <div class="sec"><span class="n">4.</span><span class="kr">컷별 묘사</span></div>

      <div class="frames">
{cut_cards}
      </div>
    </div>
  </div>

</div>
</body>
</html>
"""


def render_from_shot_plan(scenario: dict[str, Any], *, doc_title: str = "스토리보드") -> str:
    """cli_m5.py 전용 편의 함수 — M4 scenario dict(storyboard_generation.scenario_fields()가
    만든 것)에서 cast_ids/cut_count를 직접 뽑아 render_storyboard_html()을 호출한다."""
    cast_ids = [c.get("id", "") for c in (scenario.get("cast") or []) if c.get("id")]
    cut_count = len(scenario.get("scenes") or [])
    return render_storyboard_html(cast_ids, cut_count, doc_title=doc_title)
