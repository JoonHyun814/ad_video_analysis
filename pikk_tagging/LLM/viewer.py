"""VL 분석 결과 뷰어 (Flask, 포트 5007).

홈: 영상 목록 + 도메인별 대표 태그 + GT 태그
상세: 비디오 플레이어 + GT 태그 + 대표 태그 + 프레임별 태그 타임라인

python -m pikk_tagging.LLM.viewer
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_repo_root = Path(__file__).resolve().parents[2]
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

try:
    from flask import Flask, Response, jsonify, send_file, abort
except ImportError:
    raise SystemExit("pip install flask")

_BASE    = Path(r"C:\Users\llm\workspace\outputs\pikk_output\LLM\qwen_vl")
_GT_FILE = _BASE / "video_gt_tags.json"
app      = Flask(__name__)

# ── 레이블 컬러 ──────────────────────────────────────────────────────────────

_DOMAIN_COLORS: dict[str, dict[str, str]] = {
    "angle": {
        "탑뷰": "#e74c3c", "드론샷": "#9b59b6", "로우앵글": "#3498db",
        "아이레벨": "#27ae60", "하이앵글": "#f39c12", "더치앵글": "#1abc9c",
    },
    "shot_size": {
        "익스트림클로즈업": "#c0392b", "클로즈업": "#e67e22",
        "미디엄클로즈업": "#d4ac0d", "미디엄샷": "#27ae60",
        "롱샷": "#2980b9", "와이드샷": "#8e44ad", "풀샷": "#17a589",
    },
    "lighting": {
        "역광": "#e74c3c", "실루엣": "#2c3e50", "로우키": "#7f8c8d",
        "하이키": "#f39c12", "흑백": "#95a5a6", "레트로": "#d35400",
        "일반조명": "#27ae60",
    },
    "focus": {
        "아웃포커스": "#8e44ad", "딥포커스": "#2980b9", "랙포커스": "#e74c3c",
        "소프트포커스": "#f39c12", "팬포커스": "#27ae60",
    },
}

_DOMAIN_KO = {"angle": "앵글", "shot_size": "샷 크기", "lighting": "조명", "focus": "포커스"}


def _load_gt() -> dict:
    if _GT_FILE.exists():
        return json.loads(_GT_FILE.read_text(encoding="utf-8"))
    return {}


def _load_vl(video_id: str) -> dict | None:
    p = _BASE / video_id / "vl_results.json"
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


# ── 공통 CSS ─────────────────────────────────────────────────────────────────

_CSS = """
@import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/static/pretendard.css');
:root{--bg:#f7f8fa;--card:#fff;--ink:#1c2330;--sub:#5a6475;--line:#e3e7ee;--blue:#2a78d6;--blue-soft:#e8f1fc;--green:#27ae60;}
@media(prefers-color-scheme:dark){:root{--bg:#12151b;--card:#1b2029;--ink:#e8ecf3;--sub:#9aa4b5;--line:#2b3342;--blue-soft:#17293f;}}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--bg);color:var(--ink);font-family:'Pretendard','Noto Sans KR',sans-serif;font-size:14px;line-height:1.65}
.wrap{max-width:1100px;margin:0 auto;padding:28px 20px 72px}
.topnav{display:flex;align-items:center;gap:14px;margin-bottom:22px;padding-bottom:18px;border-bottom:1px solid var(--line)}
.kicker{font-size:11px;letter-spacing:.12em;color:var(--green);font-weight:700;text-transform:uppercase;margin-bottom:3px}
h1{font-size:21px;font-weight:700;letter-spacing:-.02em}
a.back{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:6px 14px;color:var(--ink);text-decoration:none;font-size:13px}
a.back:hover{border-color:var(--blue);color:var(--blue)}
.sub{font-size:13px;color:var(--sub)}
.card{background:var(--card);border:1px solid var(--line);border-radius:14px;overflow:hidden;margin-bottom:14px}
table{width:100%;border-collapse:collapse}
th{padding:10px 12px;font-size:11px;color:var(--sub);font-weight:600;border-bottom:2px solid var(--line);text-align:left;white-space:nowrap;letter-spacing:.06em;text-transform:uppercase}
td{padding:8px 12px;border-bottom:1px solid var(--line);vertical-align:middle}
tr:last-child td{border-bottom:none}
tbody tr:hover td{background:var(--blue-soft)}
.mono{font-family:monospace;font-size:12px}
.badge{display:inline-block;padding:3px 9px;border-radius:99px;font-size:12px;font-weight:700}
.domain-lbl{font-size:10px;color:var(--sub);font-weight:600;text-transform:uppercase;letter-spacing:.06em;margin-right:4px}
.vtd{padding:4px 8px;width:172px}
.vthumb{width:160px;height:90px;background:#0b0c10;border-radius:9px;cursor:pointer;display:flex;align-items:center;justify-content:center;overflow:hidden}
.vthumb:hover{opacity:.8}
.play-ic{width:34px;height:34px;border-radius:50%;background:rgba(255,255,255,.16);display:flex;align-items:center;justify-content:center;color:#fff;font-size:14px}
video.mini{width:160px;border-radius:9px;display:block;background:#000}
.player-wrap{background:#000;border-radius:14px;overflow:hidden;margin-bottom:14px}
.player-wrap video{width:100%;max-height:56vh;display:block}
.panel{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:18px 22px;margin-bottom:14px}
.panel-title{font-size:11px;color:var(--sub);font-weight:600;text-transform:uppercase;letter-spacing:.06em;margin-bottom:10px}
.tag-row{display:flex;align-items:center;gap:8px;margin-bottom:8px}
.tag-row:last-child{margin-bottom:0}
.chips{display:flex;flex-wrap:wrap;gap:6px}
.chip{display:inline-block;padding:3px 10px;border-radius:99px;font-size:12px;font-weight:600;background:rgba(42,120,214,.1);color:var(--blue);border:1px solid rgba(42,120,214,.25)}
.chip.gt{background:rgba(39,174,96,.12);color:#1a7a43;border-color:rgba(39,174,96,.4)}
.chip.none{color:var(--sub);font-style:italic;background:none;border:none}
.timeline-wrap{margin-top:14px;border-top:1px solid var(--line);padding-top:14px}
.tl-row{display:flex;align-items:center;gap:8px;margin-bottom:5px}
.tl-lbl{font-size:10px;color:var(--sub);font-weight:600;text-transform:uppercase;letter-spacing:.05em;width:72px;flex-shrink:0;text-align:right}
.tl-svg{flex:1;height:20px;display:block;border-radius:4px;background:var(--bg)}
.tl-needle-wrap{position:relative;flex:1;height:4px;background:var(--line);border-radius:2px}
.tl-needle{position:absolute;top:-4px;width:2px;height:12px;background:var(--blue);border-radius:1px;transform:translateX(-50%);transition:left .08s}
.stat-table{width:100%;border-collapse:collapse}
.stat-table td{padding:5px 8px;font-size:13px;border-bottom:1px solid var(--line)}
.stat-table tr:last-child td{border-bottom:none}
.stat-table .lbl{color:var(--sub);font-size:11px;font-weight:600;text-transform:uppercase;width:130px}
"""

# ── 홈 페이지 ─────────────────────────────────────────────────────────────────

_DOMAIN_COLORS_JS  = json.dumps(_DOMAIN_COLORS)
_DOMAIN_KO_JS      = json.dumps(_DOMAIN_KO)

_HOME_JS = f"""
const DC={_DOMAIN_COLORS_JS};
const DKO={_DOMAIN_KO_JS};

function playThumb(el,vid){{
  const cell=el.parentElement; el.style.display='none';
  let v=cell.querySelector('video');
  if(!v){{v=document.createElement('video');v.className='mini';v.controls=true;cell.appendChild(v);}}
  v.src='/media/'+vid; v.style.display='block'; v.play();
}}

function domBadge(domain, tag){{
  const color=(DC[domain]||{{}})[tag]||'#9aa4b5';
  const ko=DKO[domain]||domain;
  return `<span style="margin-right:6px"><span class="domain-lbl">${{ko}}</span>`+
         `<span class="badge" style="background:${{color}}22;color:${{color}}">${{tag}}</span></span>`;
}}

async function loadList(){{
  const vids=await fetch('/api/videos').then(r=>r.json());
  document.getElementById('count').textContent='총 '+vids.length+'개';
  const tb=document.getElementById('tbody');
  vids.forEach(v=>{{
    const tr=document.createElement('tr'); tr.style.cursor='pointer';
    const domCells=Object.entries(v.dominant_tags||{{}}).map(([d,t])=>domBadge(d,t)).join('');
    const gtChips=(v.gt_tags||[]).map(t=>`<span class="chip gt">${{t}}</span>`).join('') || '<span class="chip none">-</span>';
    tr.innerHTML=
      `<td class="mono"><a href="/video/${{v.video_id}}" style="color:var(--blue);text-decoration:none">${{v.video_id}}</a></td>`+
      `<td class="vtd"><div class="vthumb" onclick="playThumb(this,'${{v.video_id}}');event.stopPropagation()"><span class="play-ic">&#9654;</span></div></td>`+
      `<td style="font-size:12px">${{domCells||'<span class="chip none">-</span>'}}</td>`+
      `<td style="font-size:12px"><div class="chips">${{gtChips}}</div></td>`+
      `<td class="mono">${{v.model||'-'}}</td>`+
      `<td style="text-align:right">${{v.total_frames}}</td>`;
    tr.onclick=()=>location.href='/video/'+v.video_id;
    tb.appendChild(tr);
  }});
}}
loadList();
"""

_HOME_HTML = ("""<!DOCTYPE html>
<html lang="ko"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>VL 분석 뷰어</title>
<style>CSS</style></head><body>
<div class="wrap">
  <div class="topnav">
    <div>
      <div class="kicker">VL Analysis · Qwen2.5-VL Local Model</div>
      <h1>Vision LLM 도메인 분류 뷰어</h1>
    </div>
    <span class="sub" id="count"></span>
  </div>
  <div class="card">
    <table><thead><tr>
      <th>영상 ID</th><th>영상</th><th>대표 태그 (도메인별)</th>
      <th>pikk 실제 태그</th><th>모델</th><th>분석 프레임</th>
    </tr></thead><tbody id="tbody"></tbody></table>
  </div>
</div>
<script>JS</script></body></html>""").replace("CSS", _CSS).replace("JS", _HOME_JS)

# ── 상세 페이지 ───────────────────────────────────────────────────────────────

_DETAIL_JS = f"""
const VID=location.pathname.split('/').pop();
const player=document.getElementById('player');
const DC={_DOMAIN_COLORS_JS};
const DKO={_DOMAIN_KO_JS};
let _frames=[],_fmap={{}},_fps=30,_step=1,_lastIdx=-1;

function tagBadge(domain,tag){{
  const color=(DC[domain]||{{}})[tag]||'#9aa4b5';
  return `<span class="badge" style="background:${{color}}22;color:${{color}};font-size:13px">${{tag}}</span>`;
}}

function renderDominant(dominant){{
  const wrap=document.getElementById('dominant-wrap');
  wrap.innerHTML='';
  Object.entries(dominant).forEach(([d,t])=>{{
    const ko=DKO[d]||d;
    const color=(DC[d]||{{}})[t]||'#9aa4b5';
    wrap.innerHTML+=`<div class="tag-row"><span class="domain-lbl" style="width:60px">${{ko}}</span>${{tagBadge(d,t)}}</div>`;
  }});
}}

function renderGT(gtAll, gtDomain){{
  const wrap=document.getElementById('gt-wrap');
  if(!gtAll.length){{ wrap.innerHTML='<span class="chip none">GT 태그 없음</span>'; return; }}
  wrap.innerHTML=gtAll.map(t=>{{
    const hi=gtDomain.includes(t);
    return `<span class="chip${{hi?' gt':''}}">${{t}}</span>`;
  }}).join('');
}}

function updateCurrentTags(f){{
  const wrap=document.getElementById('cur-tags');
  if(!f||!f.tags){{ wrap.innerHTML='<span class="chip none">-</span>'; return; }}
  wrap.innerHTML='';
  Object.entries(f.tags).forEach(([d,t])=>{{
    const ko=DKO[d]||d;
    wrap.innerHTML+=`<div class="tag-row"><span class="domain-lbl" style="width:60px">${{ko}}</span>${{tagBadge(d,t)}}</div>`;
  }});
  document.getElementById('cur-time').textContent=`frame ${{f.frame_idx}}  (${{f.time}}s)`;
}}

function buildTimelines(domains){{
  const wrap=document.getElementById('tl-rows');
  const needle=document.getElementById('tl-needle');
  wrap.innerHTML='';
  const n=_frames.length; if(!n) return;
  const dur=_frames[n-1].time||1;

  domains.forEach(domain=>{{
    const row=document.createElement('div'); row.className='tl-row';
    const ko=DKO[domain]||domain;
    row.innerHTML=`<span class="tl-lbl">${{ko}}</span>`;
    const svg=document.createElementNS('http://www.w3.org/2000/svg','svg');
    svg.classList.add('tl-svg');
    svg.setAttribute('viewBox','0 0 800 20');
    svg.setAttribute('preserveAspectRatio','none');
    _frames.forEach((f,i)=>{{
      const tag=(f.tags||{{}})[domain];
      const color=(DC[domain]||{{}})[tag]||'#cccccc';
      const x1=(f.time/dur)*800;
      const x2=i<n-1?(_frames[i+1].time/dur)*800:800;
      const rect=document.createElementNS('http://www.w3.org/2000/svg','rect');
      rect.setAttribute('x',x1);rect.setAttribute('y',0);
      rect.setAttribute('width',Math.max(0,x2-x1));rect.setAttribute('height',20);
      rect.setAttribute('fill',color);
      svg.appendChild(rect);
    }});
    row.appendChild(svg);
    wrap.appendChild(row);
  }});
}}

player.addEventListener('timeupdate',()=>{{
  if(!_frames.length) return;
  const curTime=player.currentTime;
  let best=0;
  for(let i=0;i<_frames.length;i++){{ if(_frames[i].time<=curTime) best=i; else break; }}
  if(best===_lastIdx) return;
  _lastIdx=best; updateCurrentTags(_frames[best]);
  const dur=player.duration||1;
  const pct=(curTime/dur*100).toFixed(2);
  document.querySelectorAll('.tl-needle').forEach(el=>el.style.left=pct+'%');
}});

async function loadDetail(){{
  const data=await fetch('/api/video/'+VID).then(r=>r.json());
  if(data.error){{ document.getElementById('hdr').textContent='오류: '+data.error; return; }}
  _frames=data.frames;
  _frames.forEach((f,i)=>_fmap[f.frame_idx]=i);
  player.src='/media/'+VID;
  document.getElementById('hdr').textContent=VID;
  document.getElementById('sub').textContent=
    `${{data.total_frames}}프레임 · fps=${{data.fps}} · ${{data.model}}`;

  renderGT(data.gt_all_tags||[], data.gt_domain_tags||[]);
  renderDominant(data.dominant_tags||{{}});
  if(_frames.length) updateCurrentTags(_frames[0]);
  buildTimelines(data.target_domains||[]);

  // 통계 테이블
  const ru=data.resource_usage||{{}}, tu=data.tokens_used||{{}};
  const stats=[
    ['추론 시간', data.inference_time_sec+'s'],
    ['입력 토큰', tu.input],
    ['출력 토큰', tu.output],
    ['합계 토큰', tu.total],
    ['GPU MEM 최대', ru.gpu_memory_peak_mb+'MB'],
    ['GPU 사용률', ru.gpu_util_avg+'%'],
    ['CPU 사용률', ru.cpu_percent_avg+'%'],
  ];
  document.getElementById('stat-body').innerHTML=stats
    .map(([l,v])=>`<tr><td class="lbl">${{l}}</td><td>${{v??'-'}}</td></tr>`).join('');
}}
loadDetail();
"""

_DETAIL_HTML = ("""<!DOCTYPE html>
<html lang="ko"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>VL 상세</title>
<style>CSS</style></head><body>
<div class="wrap">
  <div class="topnav">
    <a href="/" class="back">&#8592; 목록</a>
    <div>
      <div class="kicker">VL Analysis · Qwen2.5-VL</div>
      <h1 id="hdr" style="font-size:18px">&#8230;</h1>
      <p class="sub" id="sub"></p>
    </div>
  </div>
  <div class="player-wrap"><video id="player" controls preload="metadata"></video></div>

  <div class="panel">
    <div class="panel-title">현재 프레임 태그
      <span class="sub" id="cur-time" style="margin-left:8px;font-weight:400"></span>
    </div>
    <div id="cur-tags"></div>
    <div class="timeline-wrap">
      <div class="panel-title" style="margin-bottom:8px">프레임 타임라인 (도메인별)</div>
      <div id="tl-rows"></div>
      <div class="tl-row">
        <span class="tl-lbl"></span>
        <div class="tl-needle-wrap" style="flex:1">
          <div class="tl-needle" id="tl-needle" style="left:0"></div>
        </div>
      </div>
    </div>
  </div>

  <div class="panel">
    <div class="panel-title">Pikk 실제 태그</div>
    <div class="chips" id="gt-wrap"><span class="chip none">로딩 중…</span></div>
  </div>

  <div class="panel">
    <div class="panel-title">도메인별 대표 태그 (전체 프레임 최빈값)</div>
    <div id="dominant-wrap"></div>
  </div>

  <div class="panel">
    <div class="panel-title">실행 통계</div>
    <table class="stat-table"><tbody id="stat-body"></tbody></table>
  </div>
</div>
<script>JS</script></body></html>""").replace("CSS", _CSS).replace("JS", _DETAIL_JS)


# ── 라우트 ────────────────────────────────────────────────────────────────────

@app.get("/")
def index():
    return Response(_HOME_HTML, mimetype="text/html")


@app.get("/video/<video_id>")
def detail(video_id: str):
    return Response(_DETAIL_HTML, mimetype="text/html")


@app.get("/media/<video_id>")
def media(video_id: str):
    data = _load_vl(video_id)
    if not data:
        abort(404)
    path = Path(data.get("video", ""))
    if not path.exists():
        abort(404)
    return send_file(path, mimetype="video/mp4", conditional=True)


@app.get("/api/videos")
def api_videos():
    gt = _load_gt()
    result = []
    for rp in sorted(_BASE.glob("*/vl_results.json")):
        try:
            data = json.loads(rp.read_text(encoding="utf-8"))
        except Exception:
            continue
        vid_id = rp.parent.name
        gt_info = gt.get(vid_id, {})
        result.append({
            "video_id":      vid_id,
            "model":         data.get("model", ""),
            "total_frames":  data.get("total_frames", 0),
            "fps":           data.get("fps", 2.0),
            "dominant_tags": data.get("dominant_tags", {}),
            "gt_tags":       gt_info.get("all_tags", []),
        })
    return jsonify(result)


@app.get("/api/video/<video_id>")
def api_video(video_id: str):
    data = _load_vl(video_id)
    if not data:
        return jsonify({"error": "not found"}), 404
    gt      = _load_gt()
    gt_info = gt.get(video_id, {})
    all_tags = gt_info.get("all_tags", [])
    domains  = data.get("target_domains", [])
    domain_tags = [t for d in domains for t in gt_info.get(f"{d}_tags", [])]
    return jsonify({
        "video_id":       video_id,
        "model":          data.get("model", ""),
        "fps":            data.get("fps", 2.0),
        "total_frames":   data.get("total_frames", 0),
        "target_domains": domains,
        "dominant_tags":  data.get("dominant_tags", {}),
        "frames":         data.get("frames", []),
        "inference_time_sec": data.get("inference_time_sec"),
        "tokens_used":    data.get("tokens_used", {}),
        "resource_usage": data.get("resource_usage", {}),
        "gt_all_tags":    all_tags,
        "gt_domain_tags": domain_tags,
    })


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="VL 분류 결과 뷰어")
    parser.add_argument("--port", type=int, default=5007)
    args = parser.parse_args()
    print(f"뷰어 시작: http://localhost:{args.port}")
    app.run(host="0.0.0.0", port=args.port, debug=False)


if __name__ == "__main__":
    main()
