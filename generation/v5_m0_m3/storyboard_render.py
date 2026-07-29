"""M0~M9 산출물(+`storyboard_fill.fill_extra_fields()`가 채운 추가 필드)을
`generation/AITIVE_스토리보드_데이터필드.html` 원본과 동일한 CSS·레이아웃의 HTML로 렌더링한다.

원본은 사람이 손으로 채우는 "빈 양식"이라 씬 카드 7개·촬영기법 표 12행이 고정돼 있었지만,
이 렌더러는 M9 의 실제 씬/샷 개수에 맞춰 그 블록들을 동적으로 생성한다 — 나머지(CSS, 섹션
구조, 안내문구, 이미지 슬롯)는 원본과 100% 동일하게 유지한다. 이미지 슬롯은 실제 이미지를
생성하지 않으므로(범위 밖) 원본 그대로 자리만 남긴다.

파일이 길다(원본 CSS·정적 문구 비중이 커서) — 그래도 "이 HTML 하나를 렌더링한다"는
책임 하나이므로 굳이 쪼개지 않았다.
"""
from __future__ import annotations

import html
import re


def _e(x) -> str:
    return html.escape(str(x)) if x not in (None, "") else ""


def _ln(value=None) -> str:
    return f'<div class="ln">{_e(value)}</div>'


def _ln_sm(value=None) -> str:
    return f'<div class="ln sm">{_e(value)}</div>'


def _opts(options: list[str], selected: str) -> str:
    sel = (selected or "").strip()
    return "".join(
        f'<span class="opt{" sel" if o == sel else ""}">{_e(o)}</span>' for o in options
    )


def _palette(colors) -> str:
    colors = [str(c).strip() for c in (colors or []) if c][:8]
    colors += [""] * (8 - len(colors))
    cells = []
    for i, c in enumerate(colors, 1):
        style = f' style="background:{_e(c)};color:#fff;text-shadow:0 1px 2px rgba(0,0,0,.4)"' if c else ""
        cells.append(f'<div class="sw"{style}>{_e(c) or f"색 {i}"}</div>')
    return "".join(cells)


_TIME_END_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(?:초)?\s*$")


def _last_scene_end(scenes: list[dict]) -> str:
    if not scenes:
        return ""
    m = _TIME_END_RE.search(str(scenes[-1].get("time", "")))
    return f"{m.group(1)}초" if m else ""


def _dominant_transition(scenes: list[dict]) -> str:
    counts: dict[str, int] = {}
    for s in scenes:
        t = str(s.get("transition") or "").strip()
        if t:
            counts[t] = counts.get(t, 0) + 1
    return max(counts, key=counts.get) if counts else "컷"


def _cta_goal(action: str) -> str:
    a = (action or "")
    if any(k in a for k in ("다운로드", "설치", "앱")):
        return "앱 설치"
    if any(k in a for k in ("구매", "주문", "결제")):
        return "구매"
    if any(k in a for k in ("방문", "매장", "예약")):
        return "방문"
    return "고려"


def _lens_for(lensmap: dict, size: str) -> str:
    return lensmap.get(size) or lensmap.get("default") or ""


_HEAD_CSS = """<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>스토리보드 — AITIVE 자동 채움</title>
<style>
  @import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.css');

  :root{
    --primary-700:#4c25d9; --primary-600:rgb(95,58,242); --primary-500:#7a5cf5;
    --primary-100:#ece7fe; --primary-50:#f5f2ff;
    --gray-900:#14151a; --gray-800:#1f2129; --gray-700:#33353f; --gray-600:#4b4e5a;
    --gray-500:#6b6e7b; --gray-400:#9498a5; --gray-300:#c7cad3; --gray-200:#e3e5ea;
    --gray-100:#f0f1f4; --gray-50:#f7f8fa; --white:#fff;
    --req:#c0392b; --req-bg:#fceae5;
    --outline:inset 0 0 0 1px var(--gray-200);
    --shadow-sm:0 1px 2px rgba(20,21,26,.06), 0 1px 3px rgba(20,21,26,.04);
    --shadow-md:0 2px 8px rgba(20,21,26,.08), 0 1px 3px rgba(20,21,26,.05);
    --font:"Pretendard","Pretendard Variable",Inter,-apple-system,system-ui,sans-serif;
    --mono:ui-monospace,"SF Mono",Menlo,monospace;
  }
  *{box-sizing:border-box;margin:0;padding:0}
  body{font-family:var(--font);background:var(--gray-50);color:var(--gray-900);
       line-height:1.5;-webkit-font-smoothing:antialiased;letter-spacing:-.01em;padding:24px}

  .guide{width:1800px;margin:0 auto 16px;background:var(--gray-900);color:var(--white);
         padding:14px 20px;border-radius:12px;display:flex;gap:22px;align-items:center;flex-wrap:wrap;
         box-shadow:var(--shadow-md)}
  .guide h1{font-size:.92rem;font-weight:800;letter-spacing:-.02em}
  .guide .key{display:flex;align-items:center;gap:7px;font-size:.68rem;color:var(--gray-400)}
  .guide .chip{font-size:.58rem;font-weight:800;letter-spacing:.06em;padding:2px 8px;border-radius:5px;
               border:1px dashed #4a4d58;background:#22242c;color:#c9ccd4}
  .guide .chipline{width:26px;height:0;border-bottom:1px solid #4a4d58}
  .guide .spacer{flex:1}
  .guide p{font-size:.68rem;color:var(--gray-400)}
  .guide p b{color:var(--primary-500)}

  .sheet{width:1800px;margin:0 auto;background:var(--white);border-radius:16px;overflow:hidden;
         box-shadow:var(--outline),var(--shadow-md)}

  .title{border-bottom:1px solid var(--gray-200);padding:20px 24px;display:flex;
         align-items:flex-start;gap:20px;flex-wrap:wrap;background:var(--gray-50)}
  .title h1{font-size:1.1rem;font-weight:800;white-space:nowrap;letter-spacing:-.03em;padding-top:8px}
  .title .tf{flex:1;min-width:200px}
  .title .tf .k{font-size:.56rem;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:var(--gray-500)}
  .title .tf .ln{border-bottom:1px solid var(--gray-300);min-height:20px;margin-top:3px}

  .row{display:grid;border-bottom:1px solid var(--gray-200)}
  .row:last-child{border-bottom:none}
  .r1{grid-template-columns:1fr 1fr}
  .r2{grid-template-columns:minmax(0,0.8fr) minmax(0,2.2fr)}
  .r3{grid-template-columns:1fr 1fr 1.2fr 0.8fr}
  .cell{padding:20px 22px 24px;border-right:1px solid var(--gray-200)}
  .cell:last-child{border-right:none}

  .sec{display:flex;align-items:center;gap:9px;margin-bottom:16px;flex-wrap:wrap}
  .sec .n{font-size:.66rem;font-weight:800;color:var(--white);background:var(--primary-600);
          border-radius:6px;padding:3px 8px;letter-spacing:.04em;line-height:1.2}
  .sec h2{font-size:.95rem;font-weight:800;text-transform:uppercase;letter-spacing:-.01em}
  .sec .note{font-size:.66rem;color:var(--gray-400);font-weight:500;letter-spacing:0;text-transform:none}

  .sublab{font-size:.6rem;font-weight:700;letter-spacing:.1em;text-transform:uppercase;
          color:var(--gray-400);margin:16px 0 8px}
  .sublab span{text-transform:none;letter-spacing:0;font-weight:500;color:var(--gray-400)}

  .slot{border:1.5px dashed var(--gray-300);border-radius:10px;background:var(--gray-50);
        display:flex;flex-direction:column;align-items:center;justify-content:center;
        text-align:center;padding:10px 8px;gap:4px;min-height:64px}
  .slot .icn{font-size:.62rem;font-weight:800;letter-spacing:.12em;padding:2px 8px;border-radius:5px;
             border:1px solid var(--primary-100);color:var(--primary-600);background:var(--primary-50)}
  .slot .what{font-size:.66rem;font-weight:700;color:var(--gray-700);line-height:1.4}
  .slot .hint{font-size:.58rem;color:var(--gray-400);line-height:1.4}
  .slot.tall{min-height:150px} .slot.mid{min-height:110px} .slot.wide{min-height:90px}
  .cap{font-size:.56rem;font-weight:700;text-align:center;margin-top:6px;color:var(--gray-500);letter-spacing:.04em}

  .ln{border-bottom:1px solid var(--gray-300);min-height:20px;margin-top:4px;font-size:.68rem;
      color:var(--gray-800);font-weight:600;padding-bottom:2px}
  .ln.sm{min-height:16px;font-size:.62rem}
  .fieldrow{margin-bottom:14px}
  .fieldrow .k{font-size:.62rem;font-weight:700;letter-spacing:.05em;text-transform:uppercase;color:var(--gray-600)}
  .fieldrow .k em{font-style:normal;color:var(--gray-400);font-weight:500;text-transform:none;letter-spacing:0}

  .gd{font-size:.6rem;color:var(--gray-400);line-height:1.5;margin-top:3px;font-weight:500;letter-spacing:0;text-transform:none}
  .gd b{color:var(--gray-600);font-weight:700}
  .opt{display:inline-block;font-family:var(--mono);font-size:.55rem;font-weight:700;
       color:var(--primary-700);background:var(--primary-50);border:1px solid var(--primary-100);
       border-radius:4px;padding:1px 6px;margin-right:4px;letter-spacing:.02em}
  .opt.sel{background:var(--primary-600);color:#fff;border-color:var(--primary-600)}
  .req{display:inline-block;font-size:.52rem;font-weight:800;color:var(--req);background:var(--req-bg);
       border-radius:4px;padding:1px 6px;margin-left:5px;vertical-align:1px;letter-spacing:.03em}
  .mini-opt{display:block;font-family:var(--mono);font-size:.46rem;font-weight:600;
            color:var(--gray-400);letter-spacing:0;text-transform:none;margin-top:2px}

  .g2{display:grid;grid-template-columns:1fr 1fr;gap:14px}
  .g3{display:grid;grid-template-columns:repeat(3,1fr);gap:10px}
  .g5{display:grid;grid-template-columns:repeat(5,1fr);gap:8px}

  .frames{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}
  .frame{border-radius:12px;background:var(--white);box-shadow:var(--outline),var(--shadow-sm);
         padding:12px;display:flex;flex-direction:column}
  .frame.end{box-shadow:inset 0 0 0 1.5px var(--primary-100),var(--shadow-sm);background:var(--primary-50)}
  .frame .fhead{display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;gap:6px}
  .frame .fno{font-size:.62rem;font-weight:800;background:var(--primary-600);color:var(--white);
              width:20px;height:20px;border-radius:6px;display:flex;align-items:center;justify-content:center;flex:none}
  .frame.end .fno{background:var(--primary-700)}
  .frame .tc{flex:1;border-bottom:1px solid var(--gray-300);min-height:16px;font-size:.6rem;font-weight:700}
  .frame .tclab{font-size:.52rem;color:var(--gray-400);font-weight:700;letter-spacing:.06em;flex:none}
  .frame .blk{margin-top:9px;padding-top:8px;border-top:1px solid var(--gray-100)}
  .frame .blk:first-of-type{border-top:none;padding-top:0}
  .frame .mini{display:grid;grid-template-columns:repeat(4,1fr);gap:5px;margin-bottom:5px}
  .frame .mini .m{font-size:.5rem;font-weight:800;letter-spacing:.03em;color:var(--gray-500);text-transform:uppercase}
  .frame .lab{font-size:.54rem;font-weight:800;letter-spacing:.06em;color:var(--gray-500);
              text-transform:uppercase;margin-bottom:3px}
  .frame .ovbox{margin-top:9px;background:var(--gray-50);border-radius:8px;padding:8px 9px;
                box-shadow:inset 0 0 0 1px var(--gray-100)}
  .frame .ovbox .lab{color:var(--gray-500)}
  .frame .gd{font-size:.55rem;margin-top:2px}

  table{border-collapse:separate;border-spacing:0;width:100%;border-radius:10px;overflow:hidden;
        box-shadow:var(--outline)}
  th,td{padding:7px 10px;font-size:.62rem;text-align:left;vertical-align:middle;
        border-bottom:1px solid var(--gray-100)}
  th{background:var(--gray-900);color:var(--white);font-weight:600;letter-spacing:.03em;
     text-transform:uppercase;font-size:.54rem;border-bottom:none}
  td{height:30px;color:var(--gray-700)}
  tbody tr:last-child td{border-bottom:none}
  td.c{text-align:center;font-weight:700;color:var(--gray-500)}

  .pal{display:grid;grid-template-columns:repeat(8,1fr);gap:8px;margin-bottom:6px}
  .sw{aspect-ratio:1/.55;border:1.5px dashed var(--gray-300);border-radius:8px;background:var(--gray-50);
      display:flex;align-items:center;justify-content:center;font-size:.55rem;color:var(--gray-400);font-weight:700}

  .meta{display:grid;grid-template-columns:repeat(5,1fr);border-radius:12px;overflow:hidden;
        box-shadow:var(--outline)}
  .meta .m{border-right:1px solid var(--gray-200);border-bottom:1px solid var(--gray-200);padding:10px 12px}
  .meta .m:nth-child(5n){border-right:none}
  .meta .m .k{font-size:.54rem;font-weight:800;letter-spacing:.06em;text-transform:uppercase;color:var(--gray-600)}
  .meta .m .k em{font-style:normal;font-weight:500;color:var(--gray-400);text-transform:none;letter-spacing:0}
  .meta .gd{font-size:.55rem;margin-top:3px}

  @media print{
    body{background:#fff;padding:0}
    .guide{display:none}
    .sheet{width:100%;border-radius:0;box-shadow:none;border:1px solid var(--gray-300)}
  }
</style>
</head>
<body>

<div class="guide">
  <h1>스토리보드 — AITIVE 자동 채움 결과</h1>
  <div class="key"><span class="chip">IMAGE</span> 이미지가 들어가는 자리(생성 범위 밖 — 자리만 유지)</div>
  <div class="key"><span class="chipline"></span> 밑줄 = 기입란(값이 채워짐)</div>
  <div class="key"><span class="chip" style="background:#2a1f5c;border-color:#4c25d9;color:#c9b8ff">선택지</span> 강조된 값 = 선택된 값</div>
  <div class="spacer"></div>
  <p>M0~M9 산출물 기반 자동 생성 · <b style="color:#7a5cf5">generation/v5_m0_m3/storyboard_render.py</b></p>
</div>

<div class="sheet">
"""

_FOOT = """
</div>
</body>
</html>
"""


def _title_row(module0: dict, extra: dict, spec: str) -> str:
    brand = module0.get("brand", "")
    name = module0.get("productname", "")
    concept = extra.get("_conceptname", "")
    brandline = " · ".join(x for x in (brand, f"{concept}편" if concept else name) if x)
    return f'''  <div class="title">
    <h1>스토리보드</h1>
    <div class="tf"><div class="k">브랜드 / 제품<span class="req">필수</span></div><div class="gd">브랜드명 + 편(篇) 이름까지 · 예: IBK 나라사랑카드 · PX편</div>{_ln(brandline)}</div>
    <div class="tf"><div class="k">기획</div><div class="gd">이 보드를 만든 담당자</div>{_ln("AITIVE 자동 생성 파이프라인")}</div>
    <div class="tf" style="flex:1.4"><div class="k">사양 <em style="font-style:normal;font-weight:500;text-transform:none;letter-spacing:0">— 화면비 · 길이 · 씬/컷 수 · 카메라 · 렌즈</em></div>{_ln(spec)}</div>
  </div>
'''


def _sec_character(x: dict) -> str:
    c = x.get("character", {})
    return f'''  <div class="row r1">
    <div class="cell">
      <div class="sec"><span class="n">1.</span><h2>Character Reference</h2><span class="note">전 컷 동일 인물 고정 · 등장인물마다 반복</span></div>
      <div class="g2">
        <div class="fieldrow"><div class="k">인물 A — 역할 / 연령대<span class="req">필수</span></div><div class="gd">극 중 역할 + 연령대 · 예: 선임 병사 · 20대 남성</div>{_ln(c.get("roleage"))}</div>
        <div class="fieldrow"><div class="k">고유 식별자 <em>— 예: BRAND_WOMAN_01</em><span class="req">필수</span></div><div class="gd">생성 프롬프트에서 이 인물을 부르는 이름 — 전 씬에서 같은 키를 반복 호출</div>{_ln(c.get("identifier"))}</div>
      </div>
      <div class="g5" style="margin-top:10px">
        <div><div class="slot mid"><span class="icn">IMAGE</span><span class="what">정면 CU</span><span class="hint">표정 기준</span></div><div class="cap">FRONT CU</div></div>
        <div><div class="slot mid"><span class="icn">IMAGE</span><span class="what">3/4 상반신</span><span class="hint">45° 각도</span></div><div class="cap">3/4 VIEW</div></div>
        <div><div class="slot mid"><span class="icn">IMAGE</span><span class="what">측면</span><span class="hint">옆모습·목선</span></div><div class="cap">PROFILE</div></div>
        <div><div class="slot mid"><span class="icn">IMAGE</span><span class="what">정면 MS</span><span class="hint">상반신 전체</span></div><div class="cap">FRONT MS</div></div>
        <div><div class="slot mid"><span class="icn">IMAGE</span><span class="what">착용 / 접점 부위</span><span class="hint">제품이 닿는 곳</span></div><div class="cap">DETAIL AREA</div></div>
      </div>
      <div class="g2" style="margin-top:10px">
        <div><div class="slot wide"><span class="icn">IMAGE</span><span class="what">의상 디테일</span><span class="hint">원단 질감·핏 크롭</span></div><div class="cap">COSTUME DETAIL</div></div>
        <div><div class="slot wide"><span class="icn">IMAGE</span><span class="what">손동작 참조</span><span class="hint">주요 동작 손끝</span></div><div class="cap">HAND ACTION</div></div>
      </div>
      <div class="fieldrow" style="margin-top:12px"><div class="k">의상 사양 <em>— 소재 · 색 · 핏</em></div><div class="gd">소재 · 색 · 핏을 한 문장으로 — 컷마다 옷이 바뀌지 않게 고정</div>{_ln(c.get("costumespec"))}{_ln_sm()}</div>
      <div class="fieldrow"><div class="k">표정 연기 <em>— 톤 기준</em></div><div class="gd">감정이 어떻게 진행되는지 + 과장 금지선 · 예: 데드팬 → 진짜 놀람, 슬랩스틱 금지</div>{_ln(c.get("expressiondirection"))}</div>
      <div class="g2">
        <div class="fieldrow"><div class="k">시드 고정 <em>— 인물 일관성</em><span class="req">필수</span></div><div class="gd">전 씬 동일 시드값 — 인물이 컷마다 달라지는 걸 막는 장치</div>{_ln(c.get("seednote"))}</div>
        <div class="fieldrow"><div class="k">고정 규칙</div><div class="gd">얼굴 교체 · 블렌드 금지 등 일관성 제약</div>{_ln(c.get("fixedrules"))}</div>
      </div>
      <div class="sublab">인물 B <span>— 추가 인물이 있을 때</span></div>
      <div class="fieldrow" style="margin-bottom:8px">{_ln()}</div>
      <div class="g5">
        <div><div class="slot"><span class="icn">IMAGE</span><span class="what">정면</span></div><div class="cap">FRONT</div></div>
        <div><div class="slot"><span class="icn">IMAGE</span><span class="what">3/4</span></div><div class="cap">3/4</div></div>
        <div><div class="slot"><span class="icn">IMAGE</span><span class="what">측면</span></div><div class="cap">PROFILE</div></div>
        <div><div class="slot"><span class="icn">IMAGE</span><span class="what">정면 MS</span></div><div class="cap">FRONT MS</div></div>
        <div><div class="slot"><span class="icn">IMAGE</span><span class="what">디테일</span></div><div class="cap">DETAIL</div></div>
      </div>
    </div>
'''


def _sec_product(module0: dict, x: dict) -> str:
    p = x.get("product", {})
    return f'''    <div class="cell">
      <div class="sec"><span class="n">2.</span><h2>Product Reference</h2><span class="note">제품 외형 고정(LOCK) · 실물 팩샷 우선</span></div>
      <div class="g2" style="margin-bottom:10px">
        <div class="fieldrow"><div class="k">제품명<span class="req">필수</span></div><div class="gd">정식 제품명 그대로</div>{_ln(module0.get("productname"))}</div>
        <div class="fieldrow"><div class="k">외형 <em>— 용량 · 재질 · 형태</em><span class="req">필수</span></div><div class="gd">용량 · 재질 · 형태를 한 문장으로</div>{_ln(p.get("appearance") or module0.get("productappearance"))}</div>
      </div>
      <div class="g3">
        <div><div class="slot tall"><span class="icn">IMAGE</span><span class="what">제품 정면 (히어로)</span><span class="hint">전체 형태</span></div><div class="cap">FRONT / HERO</div></div>
        <div><div class="slot tall"><span class="icn">IMAGE</span><span class="what">라벨 / 각인 디테일</span><span class="hint">크롭 · 부분 노출</span></div><div class="cap">LABEL DETAIL</div></div>
        <div><div class="slot tall"><span class="icn">IMAGE</span><span class="what">마감 / 질감 매크로</span><span class="hint">표면 · 엣지</span></div><div class="cap">FINISH MACRO</div></div>
      </div>
      <div class="sublab">사용 상태 컷 <span>— 제품 타입에 따라: 변형(붓기·도포) / 착용 전후 / 작동 전후</span></div>
      <div class="g2">
        <div><div class="slot mid"><span class="icn">IMAGE</span><span class="what">사용 순간</span><span class="hint">붓기 · 착용 · 작동</span></div><div class="cap">IN-USE</div></div>
        <div><div class="slot mid"><span class="icn">IMAGE</span><span class="what">사용 후 상태</span><span class="hint">완성된 결과</span></div><div class="cap">RESULT</div></div>
      </div>
      <div class="g2" style="margin-top:12px">
        <div class="fieldrow"><div class="k">제품 색 <em>— 실물 색만 유지</em></div><div class="gd">실물 색만 — 배경 조명이 제품색을 물들이지 않게 하는 기준값</div>{_ln(p.get("color"))}</div>
        <div class="fieldrow"><div class="k">제품 타입 <em>— 변형 / 설치 / 소품</em><span class="req">필수</span></div><div class="gd">{_opts(["변형", "설치", "소품"], p.get("producttype", ""))} 이 값이 위 <b>사용 상태 컷</b> 구성을 결정</div></div>
      </div>
      <div class="fieldrow"><div class="k">네거티브 <em>— 금지 표현</em><span class="req">필수</span></div><div class="gd">전 컷 공통 금지 — 생성 아티팩트와 톤 위반을 함께 차단</div>{_ln(p.get("negative"))}{_ln_sm()}</div>
      <div class="fieldrow"><div class="k">참조 소스 <em>— 실물 팩샷 / 생성</em></div><div class="gd">{_opts(["실물 팩샷", "생성"], p.get("referencesource", ""))} 실물 팩샷이면 형태 · 로고를 생성하지 않고 그대로 주입</div></div>
    </div>
  </div>
'''


def _sec_environment(x: dict) -> str:
    e = x.get("environment", {})
    return f'''  <div class="row r2">
    <div class="cell">
      <div class="sec"><span class="n">3.</span><h2>Environment / Set</h2></div>
      <div class="slot tall"><span class="icn">IMAGE</span><span class="what">세트 전경</span><span class="hint">공간 전체 와이드</span></div>
      <div class="cap">SET — WIDE VIEW</div>
      <div class="slot tall" style="margin-top:11px"><span class="icn">IMAGE</span><span class="what">탑다운 블로킹</span><span class="hint">인물 · 가구 · 카메라 위치</span></div>
      <div class="cap">TOP-DOWN BLOCKING</div>
      <div class="fieldrow" style="margin-top:13px"><div class="k">장소<span class="req">필수</span></div><div class="gd">구체 공간 · 예: 저녁 무렵 일본식 거실</div>{_ln(e.get("place"))}</div>
      <div class="g2">
        <div class="fieldrow"><div class="k">실내 / 실외</div><div class="gd">{_opts(["실내", "실외"], e.get("indooroutdoor", ""))}</div></div>
        <div class="fieldrow"><div class="k">시간대</div><div class="gd">{_opts(["아침", "낮", "저녁", "매직아워"], e.get("timeofday", ""))} 조명 방향과 색온도의 근거</div></div>
      </div>
      <div class="fieldrow"><div class="k">인테리어 톤 <em>— 소품 범위</em></div><div class="gd">소품 범위와 색 기조 — 화면이 산만해지지 않게 제한</div>{_ln(e.get("interiortone"))}</div>
      <div class="fieldrow"><div class="k">동선 <em>— 인물 이동 경로</em></div><div class="gd">인물 이동 경로 — 씬 간 공간 연속성의 기준</div>{_ln(e.get("blocking"))}</div>
      <div class="fieldrow"><div class="k">키라이트 방향 <em>— 전 컷 계승</em><span class="req">필수</span></div><div class="gd">전 컷이 이어받는 광원 방향 — 바뀌면 같은 공간으로 안 보임</div>{_ln(e.get("keylightdirection"))}</div>
    </div>
'''


def _join_shots(shots: list[dict], key: str) -> str:
    return " / ".join(_e(sh.get(key, "")) for sh in shots) if shots else ""


def _frame(scene: dict, idx: int, is_last: bool, lensmap: dict, cta_text: str) -> str:
    shots = [s for s in (scene.get("shots") or []) if isinstance(s, dict)]
    lens_join = " / ".join(_lens_for(lensmap, sh.get("size", "")) for sh in shots) if shots else ""
    cls = "frame end" if is_last else "frame"
    what = "엔딩 — 제품 히어로" if is_last else f"씬 {idx} 화면"
    hint = '<span class="hint">CTA용 여백 확보</span>' if is_last else ""
    if is_last:
        ovbox = (f'<div class="ovbox"><div class="lab">CTA <em style="font-style:normal;'
                  f'font-weight:500;text-transform:none;letter-spacing:0">— 후반 합성</em></div>'
                  f'{_ln_sm(cta_text)}</div>')
    else:
        ovbox = (f'<div class="ovbox"><div class="lab">오버레이</div>'
                  f'<div class="gd">화면에 얹을 문구 — 영상엔 안 그리고 후반 합성</div>'
                  f'{_ln_sm(scene.get("overlay"))}</div>')
    return f'''        <div class="{cls}">
          <div class="fhead"><span class="fno">{idx}</span><span class="tclab">TIME</span><span class="tc">{_e(scene.get("time"))}</span></div>
          <div class="slot wide"><span class="icn">IMAGE</span><span class="what">{_e(what)}</span>{hint}</div>
          <div class="blk"><div class="lab">화면 묘사</div><div class="gd">피사체 + 동작 · 직전 컷과 뭐가 다른지 · <b>화면 글자는 쓰지 않음</b></div>{_ln_sm(scene.get("visual"))}{_ln_sm(scene.get("brief"))}</div>
          <div class="blk">
            <div class="mini"><div class="m">Size<span class="mini-opt">WS·MS·CU</span></div><div class="m">Angle<span class="mini-opt">eye·low·high·top·pov</span></div><div class="m">Cut<span class="mini-opt">hard·insert</span></div><div class="m">Sec<span class="mini-opt">초</span></div></div>
            <div class="mini">{_ln_sm(_join_shots(shots, "size"))}{_ln_sm(_join_shots(shots, "angle"))}{_ln_sm(_join_shots(shots, "cut"))}{_ln_sm(_join_shots(shots, "sec"))}</div>
            <div class="lab" style="margin-top:5px">렌즈</div>{_ln_sm(lens_join)}
          </div>
          {ovbox}
        </div>
'''


def _vo_card(m5: dict, scenes: list[dict]) -> str:
    lines = [str(ln.get("line", "")) for ln in (m5.get("script") or []) if isinstance(ln, dict)][:5]
    narration = "".join(_ln_sm(ln) for ln in lines) if lines else _ln_sm("VO 없음") + "".join(_ln_sm() for _ in range(4))
    bgm = " → ".join(f'{s.get("time", "")} {s.get("mood", "")}'.strip() for s in scenes if s.get("mood"))
    return f'''        <div class="frame" style="background:var(--gray-50);box-shadow:inset 0 0 0 1.5px var(--gray-200)">
          <div class="fhead"><span class="fno" style="background:var(--gray-500)">VO</span><span class="tclab">내레이션 · BGM</span></div>
          <div class="blk" style="margin-top:2px"><div class="lab">내레이션</div><div class="gd">씬별 대사 · 없으면 "VO 없음"으로 명시</div>
            {narration}
          </div>
          <div class="blk"><div class="lab">BGM 흐름</div><div class="gd">음악 전개 + SFX 포인트 · 예: 잔잔한 피아노 → 마무리 훅</div>{_ln_sm(bgm)}{_ln_sm()}</div>
        </div>
'''


def _sec_storyboard(m5: dict, m9: dict, x: dict) -> str:
    scenes = [s for s in ((m9 or {}).get("scenes") or []) if isinstance(s, dict)]
    lensmap = (x.get("camera") or {}).get("lensbysize") or {}
    cta_text = (m5.get("cta") or {}).get("text", "")
    frames = "".join(_frame(s, i, i == len(scenes), lensmap, cta_text) for i, s in enumerate(scenes, 1))
    frames += _vo_card(m5, scenes)
    return f'''    <div class="cell">
      <div class="sec"><span class="n">4.</span><h2>Storyboard</h2><span class="note">컷마다 사이즈·앵글 다르게 · 사용 완결 컷 최소 1개 · 화면 글자 금지</span></div>
      <div class="frames">
{frames}      </div>
      <div class="g2" style="margin-top:13px">
        <div class="fieldrow"><div class="k">감정 곡선 <em>— 시간대별 감정</em></div><div class="gd">시간대별 감정 진행 — 골과 정점을 명시</div>{_ln(m9.get("emotioncurve"))}</div>
        <div class="fieldrow"><div class="k">사용 완결 컷 <em>— 제품을 실제로 쓰는 씬 번호</em><span class="req">필수</span></div><div class="gd">제품을 실제로 쓰는 씬 번호 — <b>최소 1개 필수</b></div>{_ln(m9.get("usagecutscene"))}</div>
      </div>
      <div class="fieldrow"><div class="k">화면 글자 <em>— 자막 · 로고 · QR · CTA는 후반 합성, 보드에 그리지 않음</em></div><div class="gd">기본값은 전부 후반 합성 — 보드·영상에는 글자를 그리지 않음</div>{_ln("전부 후반 합성(자막/로고/QR/CTA)")}</div>
    </div>
  </div>
'''


def _sec_camera(m9: dict, x: dict) -> str:
    scenes = [s for s in ((m9 or {}).get("scenes") or []) if isinstance(s, dict)]
    cam = x.get("camera", {})
    lensmap = cam.get("lensbysize") or {}
    rows = []
    for s in scenes:
        shots = [sh for sh in (s.get("shots") or []) if isinstance(sh, dict)]
        lens = _lens_for(lensmap, shots[0].get("size", "")) if shots else _lens_for(lensmap, "")
        rows.append(f'<tr><td class="c">{_e(s.get("no"))}</td><td>{_e(s.get("shot"))}</td><td>{_e(lens)}</td></tr>')
    return f'''  <div class="row r3">
    <div class="cell">
      <div class="sec"><span class="n">5.</span><h2>Camera Work</h2></div>
      <div class="fieldrow"><div class="k">기본 원칙</div><div class="gd">전 컷을 관통하는 촬영 규칙 · 예: 고정 카메라 · 아이레벨 · 얕은 심도</div>{_ln(cam.get("principle"))}{_ln_sm()}</div>
      <table style="margin-top:9px">
        <thead><tr><th style="width:15%">씬</th><th>무브 · 프레이밍</th><th style="width:27%">렌즈</th></tr></thead>
        <tbody>
{"".join(rows)}
        </tbody>
      </table>
      <div class="fieldrow" style="margin-top:11px"><div class="k">전환 <em>— 하드컷 기본 · 디졸브 금지</em></div><div class="gd">{_opts(["컷", "모션 컷", "디졸브"], _dominant_transition(scenes))} 편집 전환의 기본값과 금지</div></div>
      <div class="fieldrow"><div class="k">배정 원칙 <em>— 인접 컷 대비</em></div><div class="gd">렌즈를 어떤 기준으로 나눠 붙였는지 · 예: 이동 광각 · 정지 표준</div>{_ln(cam.get("assignmentprinciple"))}</div>
    </div>
'''


def _sec_lighting(x: dict) -> str:
    li = x.get("lighting", {})
    return f'''    <div class="cell">
      <div class="sec"><span class="n">6.</span><h2>Lighting / Mood</h2></div>
      <div class="g2">
        <div><div class="slot mid"><span class="icn">IMAGE</span><span class="what">키라이트</span><span class="hint">주광원 방향</span></div><div class="cap">KEY LIGHT</div></div>
        <div><div class="slot mid"><span class="icn">IMAGE</span><span class="what">필 / 디퓨전</span><span class="hint">부드러움 정도</span></div><div class="cap">FILL</div></div>
        <div><div class="slot mid"><span class="icn">IMAGE</span><span class="what">인물 조명 무드</span><span class="hint">얼굴에 닿는 빛</span></div><div class="cap">SUBJECT MOOD</div></div>
        <div><div class="slot mid"><span class="icn">IMAGE</span><span class="what">제품 조명 무드</span><span class="hint">반사 · 하이라이트</span></div><div class="cap">PRODUCT MOOD</div></div>
      </div>
      <div class="fieldrow" style="margin-top:12px"><div class="k">조명 세팅 <em>— 클립 전체에 하나의 룩만</em><span class="req">필수</span></div><div class="gd"><b>클립 전체에 하나의 룩만</b> — 컷마다 바뀌면 다른 광고로 보임</div>{_ln(li.get("setup"))}</div>
      <div class="fieldrow"><div class="k">무드 키워드</div><div class="gd">조명 · 연출이 만들 정서 · 예: 조용한 확신 · 절제</div>{_ln(li.get("moodkeywords"))}</div>
      <div class="fieldrow"><div class="k">금지 <em>— 과채도 · 색온도 수치 표기 등</em></div><div class="gd">조명 · 색 관련 금지 — 색온도 수치 표기 금지가 기본</div>{_ln(li.get("forbidden"))}</div>
    </div>
'''


def _sec_technique(m9: dict, x: dict) -> str:
    scenes = [s for s in ((m9 or {}).get("scenes") or []) if isinstance(s, dict)]
    lensmap = (x.get("camera") or {}).get("lensbysize") or {}
    insertnote = (x.get("camera") or {}).get("insertnote", "")
    rows = []
    i = 0
    for s in scenes:
        shots = [sh for sh in (s.get("shots") or []) if isinstance(sh, dict)] or [
            {"desc": s.get("visual", ""), "size": "", "angle": "", "cut": "", "sec": ""}
        ]
        for sh in shots:
            i += 1
            sac = " · ".join(x for x in (sh.get("size", ""), sh.get("angle", ""), sh.get("cut", "")) if x)
            lens = _lens_for(lensmap, sh.get("size", ""))
            rows.append(f'<tr><td class="c">{i}</td><td class="c">{_e(s.get("no"))}</td>'
                        f'<td>{_e(sh.get("desc"))}</td><td>{_e(sac)}</td><td>{_e(lens)}</td>'
                        f'<td>{_e(sh.get("sec"))}</td></tr>')
    return f'''    <div class="cell">
      <div class="sec"><span class="n">7.</span><h2>Shooting Technique</h2><span class="note">컷 단위 · 15초 기준 8~12컷</span></div>
      <table>
        <thead><tr><th style="width:5%">#</th><th style="width:7%">씬</th><th>샷 / 액션</th><th style="width:19%">사이즈 · 앵글 · 컷</th><th style="width:16%">렌즈</th><th style="width:7%">초</th></tr></thead>
        <tbody>
{"".join(rows)}
        </tbody>
      </table>
      <div class="fieldrow" style="margin-top:11px"><div class="k">인서트 <em>— 인물 없는 제품 디테일 컷</em></div><div class="gd">인물 없는 제품 디테일 컷의 렌즈 레시피 · 예: 매크로 · 랙포커스</div>{_ln(insertnote)}</div>
    </div>
'''


def _sec_credits(module0: dict, m5: dict, x: dict) -> str:
    toneregister = m5.get("toneregister", "")
    cta_goal = _cta_goal((m5.get("cta") or {}).get("action", ""))
    return f'''    <div class="cell">
      <div class="sec"><span class="n">8.</span><h2>Credits</h2></div>
      <div class="fieldrow"><div class="k">Brand</div><div class="gd">광고주</div>{_ln(module0.get("brand"))}</div>
      <div class="fieldrow"><div class="k">기획</div><div class="gd">이 보드를 만든 담당자</div>{_ln("AITIVE 자동 생성 파이프라인")}</div>
      <div class="fieldrow"><div class="k">Agency</div><div class="gd">광고대행사</div>{_ln()}</div>
      <div class="fieldrow"><div class="k">Director</div><div class="gd">연출 — AI 생성 건에서는 <b>스타일 앵커</b>로 표기</div>{_ln("video_style 프리셋(cli --style)")}</div>
      <div class="fieldrow"><div class="k">Cinematographer / DP</div><div class="gd">촬영 · 조명 · 룩 기준</div>{_ln("N/A(AI 이미지-투-비디오 생성)")}</div>
      <div class="fieldrow"><div class="k">Production</div><div class="gd">제작사 또는 생성 파이프라인</div>{_ln("generation/v5_m0_m3 (M0~M9)")}</div>
      <div class="sublab" style="margin-top:12px">브랜드 톤</div>
      {_ln(toneregister)}{_ln_sm()}{_ln_sm()}
      <div class="fieldrow" style="margin-top:11px"><div class="k">전환 목표</div><div class="gd">{_opts(["구매", "고려", "앱 설치", "방문"], cta_goal)} 광고가 유도하는 최종 행동</div></div>
    </div>
  </div>
'''


def _frame_size_summary(scenes: list[dict]) -> str:
    sizes: list[str] = []
    for s in scenes:
        for sh in (s.get("shots") or []):
            if isinstance(sh, dict) and sh.get("size") and sh["size"] not in sizes:
                sizes.append(sh["size"])
    if not sizes:
        return ""
    return sizes[0] if len(sizes) == 1 else f'혼합 {"/".join(sizes)}'


def _sec_metadata(module0: dict, m1: dict, m5: dict, m9: dict, x: dict) -> str:
    scenes = [s for s in ((m9 or {}).get("scenes") or []) if isinstance(s, dict)]
    meta = x.get("metadata", {})
    env = x.get("environment", {})
    duration = f"{_last_scene_end(scenes)} · {len(scenes)}씬 · {sum(len(s.get('shots') or []) or 1 for s in scenes)}컷"
    return f'''  <div class="row">
    <div class="cell">
      <div class="sec"><span class="n">9.</span><h2>Metadata Card</h2><span class="note">보드 분류 · 검색용</span></div>
      <div class="sublab">컬러 팔레트 <span>— 보드 전체에서 뽑은 무드 컬러</span></div>
      <div class="pal">{_palette(meta.get("palette"))}</div>
      <div class="fieldrow" style="margin:12px 0 13px"><div class="k">Tags <em>— 분위기 키워드</em></div><div class="gd">분위기 키워드 — 자산 검색의 1차 키</div>{_ln(meta.get("tags"))}</div>
      <div class="meta">
        <div class="m"><div class="k">Genre <em>장르</em></div><div class="gd">최상위 광고 분류 · 예: 금융 브랜드 필름 / DR-CTV</div>{_ln_sm(meta.get("genre"))}</div>
        <div class="m"><div class="k">Sub-genre <em>서브장르</em></div><div class="gd">장르 안의 세부 성격 · 예: 예능식 콩트 내러티브</div>{_ln_sm(meta.get("subgenre"))}</div>
        <div class="m"><div class="k">Brand Tone <em>브랜드 톤</em></div><div class="gd">브랜드가 주려는 정서 — 전략에서 상속</div>{_ln_sm(m5.get("toneregister"))}</div>
        <div class="m"><div class="k">Ad Format <em>광고 포맷</em></div><div class="gd">송출 형태와 길이 · 예: DR-CTV :15</div>{_ln_sm(meta.get("adformat"))}</div>
        <div class="m"><div class="k">Product Integration <em>제품 노출</em></div><div class="gd">제품이 담기는 방식 · 예: 히어로 제품 · 사용 완결 컷</div>{_ln_sm(meta.get("productintegration"))}</div>

        <div class="m"><div class="k">Actors <em>출연</em></div><div class="gd">캐스팅 구성 · 예: 선임 1 + 후임 2</div>{_ln_sm(meta.get("actors"))}</div>
        <div class="m"><div class="k">Aspect Ratio <em>화면비</em></div><div class="gd">{_opts(["16:9", "9:16", "1:1"], meta.get("aspectratio") or "16:9")}</div></div>
        <div class="m"><div class="k">Format <em>포맷</em></div><div class="gd">촬영 · 저장 방식 · 예: 디지털 · 이미지-투-비디오</div>{_ln_sm("디지털 · 이미지-투-비디오(AI 생성)")}</div>
        <div class="m"><div class="k">Frame Size <em>프레임 사이즈</em></div><div class="gd">보드 전체에서 쓰인 사이즈 범위 · 예: 혼합 WS/MS/CU</div>{_ln_sm(_frame_size_summary(scenes))}</div>
        <div class="m"><div class="k">Shot Type <em>샷 타입</em></div><div class="gd">촬영 구성 방식 · 예: 클린 싱글 + 그룹샷</div>{_ln_sm(meta.get("shottype"))}</div>

        <div class="m"><div class="k">Lens Size <em>렌즈 사이즈</em></div><div class="gd">사용 화각대 · 예: 24–100mm</div>{_ln_sm(meta.get("lenssize"))}</div>
        <div class="m"><div class="k">Composition <em>구도</em></div><div class="gd">화면 배치 원칙 · 예: 3분할 · CTA 여백</div>{_ln_sm(meta.get("composition"))}</div>
        <div class="m"><div class="k">Lighting <em>조명</em></div><div class="gd">조명 세팅 요약 · 예: 측창 자연광 키</div>{_ln_sm(meta.get("lightingsummary"))}</div>
        <div class="m"><div class="k">Lighting Type <em>조명 타입</em></div><div class="gd">광원의 성질 · 예: 데이라이트 / 형광등</div>{_ln_sm(meta.get("lightingtype"))}</div>
        <div class="m"><div class="k">Time of Day <em>시간대</em></div><div class="gd">{_opts(["아침", "낮", "저녁", "매직아워"], env.get("timeofday", ""))}</div></div>

        <div class="m"><div class="k">Interior / Exterior <em>실내·실외</em></div><div class="gd">{_opts(["실내", "실외"], env.get("indooroutdoor", ""))}</div></div>
        <div class="m"><div class="k">Location Type <em>로케이션 타입</em></div><div class="gd">{_opts(["세트", "로케이션"], meta.get("locationtype", ""))}</div></div>
        <div class="m"><div class="k">Set <em>세트</em></div><div class="gd">구체 공간, 계층으로 · 예: 부대 &gt; 생활관 + PX</div>{_ln_sm(meta.get("set"))}</div>
        <div class="m"><div class="k">Camera <em>카메라</em></div><div class="gd">카메라 바디 · 예: ARRI Alexa 35</div>{_ln_sm(meta.get("camerabody"))}</div>
        <div class="m"><div class="k">Lens <em>렌즈</em></div><div class="gd">렌즈군 명칭 · 예: Cooke S7/i</div>{_ln_sm(meta.get("lens"))}</div>

        <div class="m"><div class="k">Film Stock / Resolution <em>필름 스톡·해상도</em></div><div class="gd">색감 레퍼런스 + 최종 해상도</div>{_ln_sm(meta.get("filmstock"))}</div>
        <div class="m"><div class="k">Time Period <em>시대</em></div><div class="gd">극의 시대 배경 · 예: 현대(2020년대)</div>{_ln_sm("현대(2020년대)")}</div>
        <div class="m"><div class="k">Category <em>카테고리</em></div><div class="gd">제품 카테고리, 계층으로</div>{_ln_sm(module0.get("category"))}</div>
        <div class="m"><div class="k">Target <em>타깃</em></div><div class="gd">타깃 인구 · 상황</div>{_ln_sm(((m1 or {}).get("target") or {}).get("label"))}</div>
        <div class="m"><div class="k">Duration <em>길이 · 씬/컷 수</em></div><div class="gd">총 길이와 씬/컷 수 · 예: 15초 · 6씬 · 11컷</div>{_ln_sm(duration)}</div>
      </div>
    </div>
  </div>
'''


def render_storyboard_html(module0: dict, m1: dict, m2: dict, m4: dict, m5: dict, m9: dict,
                            extra: dict) -> str:
    """M0~M9 산출물 + `storyboard_fill.fill_extra_fields()` 결과로 완성된 스토리보드 HTML을
    문자열로 반환한다. `extra` 는 `storyboard_fill._SCHEMA` 와 같은 형태를 기대한다."""
    module0, m1, m2, m4, m5, m9 = module0 or {}, m1 or {}, m2 or {}, m4 or {}, m5 or {}, m9 or {}
    extra = extra or {}
    scenes = [s for s in (m9.get("scenes") or []) if isinstance(s, dict)]
    shot_count = sum(len(s.get("shots") or []) or 1 for s in scenes)
    selected = (m4.get("selected") or [{}])[0]
    extra["_conceptname"] = selected.get("concept", "")
    aspect = (extra.get("metadata") or {}).get("aspectratio") or "16:9"
    spec = f"{aspect} · {_last_scene_end(scenes)} · {len(scenes)}씬 {shot_count}컷 · AI 생성(카메라/렌즈 N/A)"

    body = (
        _title_row(module0, extra, spec)
        + _sec_character(extra)
        + _sec_product(module0, extra)
        + _sec_environment(extra)
        + _sec_storyboard(m5, m9, extra)
        + _sec_camera(m9, extra)
        + _sec_lighting(extra)
        + _sec_technique(m9, extra)
        + _sec_credits(module0, m5, extra)
        + _sec_metadata(module0, m1, m5, m9, extra)
    )
    return _HEAD_CSS + body + _FOOT

