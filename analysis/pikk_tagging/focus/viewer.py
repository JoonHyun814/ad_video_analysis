"""포커스 분류 결과 뷰어 (Flask, 포트 5005).

python -m pikk_tagging.focus.viewer
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

_BASE    = Path(r"C:\Users\llm\workspace\outputs\pikk_output\focus")
_GT_FILE = _BASE / "video_gt_tags.json"
app      = Flask(__name__)

_FOCUS_KW = ["포커스", "아웃포커", "보케", "피사계", "랙포커", "딥포커", "블러", "포커싱", "심도"]

_LABEL_COLORS = {
    "out_of_focus": ("#7f8c8d", "#f2f3f4"),
    "shallow_dof":  ("#8e44ad", "#f5eef8"),
    "rack_focus":   ("#e74c3c", "#fdedec"),
    "deep_focus":   ("#2980b9", "#eaf4fb"),
    "normal":       ("#27ae60", "#e9f7ef"),
}


def _load_gt() -> dict:
    if _GT_FILE.exists():
        return json.loads(_GT_FILE.read_text(encoding="utf-8"))
    return {}


_CSS = """
@import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/static/pretendard.css');
:root{--bg:#f7f8fa;--card:#fff;--ink:#1c2330;--sub:#5a6475;--line:#e3e7ee;--blue:#2a78d6;--blue-soft:#e8f1fc;--green:#27ae60;}
@media(prefers-color-scheme:dark){:root{--bg:#12151b;--card:#1b2029;--ink:#e8ecf3;--sub:#9aa4b5;--line:#2b3342;--blue-soft:#17293f;}}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--bg);color:var(--ink);font-family:'Pretendard','Apple SD Gothic Neo','Noto Sans KR',sans-serif;font-size:14px;line-height:1.65}
.wrap{max-width:1100px;margin:0 auto;padding:28px 20px 72px}
.topnav{display:flex;align-items:center;gap:14px;margin-bottom:22px;padding-bottom:18px;border-bottom:1px solid var(--line)}
.kicker{font-size:11px;letter-spacing:.12em;color:var(--green);font-weight:700;text-transform:uppercase;margin-bottom:3px}
h1{font-size:21px;font-weight:700;letter-spacing:-.02em}
a.back{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:6px 14px;color:var(--ink);text-decoration:none;font-size:13px}
a.back:hover{border-color:var(--blue);color:var(--blue)}
.sub{font-size:13px;color:var(--sub)}
.card{background:var(--card);border:1px solid var(--line);border-radius:14px;overflow:hidden}
table{width:100%;border-collapse:collapse}
th{padding:10px 12px;font-size:11px;color:var(--sub);font-weight:600;border-bottom:2px solid var(--line);text-align:left;white-space:nowrap;letter-spacing:.06em;text-transform:uppercase}
td{padding:8px 12px;border-bottom:1px solid var(--line);vertical-align:middle}
tr:last-child td{border-bottom:none}
tbody tr:hover td{background:var(--blue-soft);transition:background .1s}
.mono{font-family:monospace;font-size:12px}
.badge{display:inline-block;padding:3px 10px;border-radius:99px;font-size:12px;font-weight:700;letter-spacing:.04em}
.vtd{padding:4px 8px;width:172px}
.vthumb{width:160px;height:90px;background:#0b0c10;border-radius:9px;cursor:pointer;display:flex;align-items:center;justify-content:center;overflow:hidden;transition:opacity .15s}
.vthumb:hover{opacity:.8}
.play-ic{width:34px;height:34px;border-radius:50%;background:rgba(255,255,255,.16);display:flex;align-items:center;justify-content:center;color:#fff;font-size:14px}
video.mini{width:160px;border-radius:9px;display:block;background:#000}
.dist-wrap{display:flex;height:8px;border-radius:4px;overflow:hidden;gap:1px;min-width:140px}
.dist-seg{height:100%}
.player-wrap{background:#000;border-radius:14px;overflow:hidden;margin-bottom:14px}
.player-wrap video{width:100%;max-height:56vh;display:block}
#stats-panel{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:18px 22px}
.panel-header{display:flex;align-items:center;gap:14px;margin-bottom:16px;flex-wrap:wrap}
#cur-label{font-size:22px;font-weight:800;letter-spacing:-.01em;padding:4px 16px;border-radius:10px;transition:background .12s,color .12s}
.stat-row{display:grid;grid-template-columns:140px 1fr 90px;align-items:center;gap:12px;margin-bottom:10px}
.stat-row:last-child{margin-bottom:0}
.stat-label{font-size:11px;color:var(--sub);font-weight:600;text-transform:uppercase;letter-spacing:.06em}
.bar-wrap{position:relative;height:10px;background:var(--line);border-radius:5px}
.bar-fill{position:absolute;top:0;height:100%;border-radius:5px;transition:left .08s,width .08s,background .08s}
.stat-val{font-family:monospace;font-size:12px;text-align:right;color:var(--ink)}
.timeline-wrap{margin-top:14px;border-top:1px solid var(--line);padding-top:14px}
.timeline-lbl{font-size:11px;color:var(--sub);font-weight:600;text-transform:uppercase;letter-spacing:.06em;margin-bottom:6px}
#timeline-svg{width:100%;height:48px;display:block;border-radius:6px;background:var(--bg);overflow:hidden}
#t-cursor{position:relative;width:100%;height:4px;margin-top:3px;background:var(--line);border-radius:2px;overflow:visible}
#t-needle{position:absolute;top:-4px;width:2px;height:12px;background:var(--blue);border-radius:1px;transform:translateX(-50%);transition:left .08s}
.gt-wrap{margin-top:14px;border-top:1px solid var(--line);padding-top:12px}
.gt-lbl{font-size:11px;color:var(--sub);font-weight:600;text-transform:uppercase;letter-spacing:.06em;margin-bottom:7px}
.gt-tags{display:flex;flex-wrap:wrap;gap:6px}
.gt-chip{display:inline-block;padding:3px 10px;border-radius:99px;font-size:12px;font-weight:600;background:rgba(42,120,214,.1);color:var(--blue);border:1px solid rgba(42,120,214,.25)}
.gt-chip.domain{background:rgba(142,68,173,.12);color:#6c3483;border-color:rgba(142,68,173,.4)}
.gt-none{font-size:12px;color:var(--sub);font-style:italic}
"""

_LABEL_COLORS_JS = json.dumps(_LABEL_COLORS)
_LABEL_ORDER = ["out_of_focus", "shallow_dof", "rack_focus", "deep_focus", "normal"]
_LABEL_HEX   = json.dumps({k: v[0] for k, v in _LABEL_COLORS.items()})

_HOME_JS = f"""
const COLORS={_LABEL_COLORS_JS};
const LABEL_HEX={_LABEL_HEX};
const LABEL_ORDER={json.dumps(_LABEL_ORDER)};

function playThumb(el,vid){{
  const cell=el.parentElement; el.style.display='none';
  let v=cell.querySelector('video');
  if(!v){{v=document.createElement('video');v.className='mini';v.controls=true;cell.appendChild(v);}}
  v.src='/media/'+vid; v.style.display='block'; v.play();
}}

function makeDist(counts,total){{
  const wrap=document.createElement('div'); wrap.className='dist-wrap';
  LABEL_ORDER.forEach(lbl=>{{
    const cnt=counts[lbl]||0; if(!cnt) return;
    const seg=document.createElement('div'); seg.className='dist-seg';
    seg.style.width=(cnt/total*100).toFixed(1)+'%';
    seg.style.background=LABEL_HEX[lbl]||'#ccc'; seg.title=lbl+': '+cnt;
    wrap.appendChild(seg);
  }});
  return wrap;
}}

async function loadList(){{
  const vids=await fetch('/api/videos').then(r=>r.json());
  document.getElementById('count').textContent='총 '+vids.length+'개';
  const tb=document.getElementById('tbody');
  vids.forEach(v=>{{
    const tr=document.createElement('tr'); tr.style.cursor='pointer';
    const [fg_,bg_]=COLORS[v.dominant_label]||['#9aa4b5','#f0f2f5'];
    const gtDomain=v.gt_domain_tags||[];
    const gtChips=gtDomain.length
      ? gtDomain.map(t=>`<span class="gt-chip domain">${{t}}</span>`).join('')
      : '<span class="gt-none">-</span>';
    tr.innerHTML=
      `<td class="mono"><a href="/video/${{v.video_id}}" style="color:var(--blue);text-decoration:none">${{v.video_id}}</a></td>`+
      `<td class="vtd"><div class="vthumb" onclick="playThumb(this,'${{v.video_id}}');event.stopPropagation()"><span class="play-ic">&#9654;</span></div></td>`+
      `<td><span class="badge" style="color:${{fg_}};background:${{bg_}}">${{v.dominant_label}}</span></td>`+
      `<td style="font-size:12px">${{gtChips}}</td>`+
      `<td style="text-align:right">${{v.total_frames}}</td>`+
      `<td></td>`;
    if(v.label_counts) tr.cells[5].appendChild(makeDist(v.label_counts,v.total_frames));
    tr.onclick=()=>location.href='/video/'+v.video_id;
    tb.appendChild(tr);
  }});
}}
loadList();
"""

_HOME_HTML = ("""<!DOCTYPE html>
<html lang="ko"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>포커스 뷰어</title>
<style>CSS</style></head><body>
<div class="wrap">
  <div class="topnav">
    <div>
      <div class="kicker">Focus / DOF · Laplacian Variance</div>
      <h1>포커스 분류 뷰어</h1>
    </div>
    <span class="sub" id="count"></span>
  </div>
  <div class="card">
    <table><thead><tr>
      <th>영상 ID</th><th>영상</th><th>예측 주 레이블</th>
      <th>pikk 실제 태그</th><th>분석 프레임</th><th>레이블 분포</th>
    </tr></thead><tbody id="tbody"></tbody></table>
  </div>
</div>
<script>JS</script></body></html>""").replace("CSS", _CSS).replace("JS", _HOME_JS)


_DETAIL_JS = f"""
const VID=location.pathname.split('/').pop();
const player=document.getElementById('player');
const COLORS={_LABEL_COLORS_JS};
let _frames=[],_fmap={{}},_fps=30,_step=30,_lastIdx=-1;

function updateBar(id,value,maxVal,color){{
  const el=document.getElementById('bar-'+id);
  el.style.left='0';el.style.width=Math.min(100,maxVal>0?value/maxVal*100:0)+'%';el.style.background=color;
}}

function updatePanel(f){{
  if(!f||!f.stats) return;
  const s=f.stats; const lbl=f.label||'normal';
  const [fg,bg]=COLORS[lbl]||['#9aa4b5','#f0f2f5'];
  const labelEl=document.getElementById('cur-label');
  labelEl.textContent=lbl; labelEl.style.color=fg; labelEl.style.background=bg;
  document.getElementById('cur-time').textContent=`frame ${{f.frame}} (${{f.time}}s)`;

  const maxSharp=2000;
  updateBar('global_s',s.global_sharpness,maxSharp,'#2980b9');
  document.getElementById('val-global_s').textContent=s.global_sharpness.toFixed(0);
  updateBar('center_s',s.center_sharpness,maxSharp,'#8e44ad');
  document.getElementById('val-center_s').textContent=s.center_sharpness.toFixed(0);
  updateBar('bg_s',s.bg_sharpness,maxSharp,'#7f8c8d');
  document.getElementById('val-bg_s').textContent=s.bg_sharpness.toFixed(0);
  updateBar('cb_ratio',s.center_bg_ratio,6,'#e74c3c');
  document.getElementById('val-cb_ratio').textContent=s.center_bg_ratio.toFixed(2);
  updateBar('delta',s.sharpness_delta,1500,'#e67e22');
  document.getElementById('val-delta').textContent=s.sharpness_delta.toFixed(0);

  const dur=player.duration||1;
  document.getElementById('t-needle').style.left=(Math.min(100,(f.time/dur)*100))+'%';
}}

function buildTimeline(){{
  const svg=document.getElementById('timeline-svg');
  const n=_frames.length; if(!n) return;
  const W=svg.clientWidth||800,H=48;
  svg.setAttribute('viewBox','0 0 '+W+' '+H);
  const dur=_frames[n-1].time||1;
  const maxS=Math.max(..._frames.map(f=>f.stats.global_sharpness),1);
  _frames.forEach((f,i)=>{{
    if(i===n-1) return;
    const [fg]=COLORS[f.label]||['#9aa4b5'];
    const x1=(_frames[i].time/dur)*W,x2=(_frames[i+1].time/dur)*W;
    const rect=document.createElementNS('http://www.w3.org/2000/svg','rect');
    rect.setAttribute('x',x1);rect.setAttribute('y',0);
    rect.setAttribute('width',x2-x1);rect.setAttribute('height',H);
    rect.setAttribute('fill',fg);rect.setAttribute('opacity','0.3');
    svg.appendChild(rect);
  }});
  const pts=_frames.map(f=>[(f.time/dur)*W,H-(f.stats.global_sharpness/maxS)*H]);
  const path=document.createElementNS('http://www.w3.org/2000/svg','path');
  path.setAttribute('d','M'+pts.map(p=>p[0].toFixed(1)+','+p[1].toFixed(1)).join(' L'));
  path.setAttribute('fill','none');path.setAttribute('stroke','var(--ink)');
  path.setAttribute('stroke-width','1.5');path.setAttribute('opacity','0.6');
  svg.appendChild(path);
}}

player.addEventListener('timeupdate',()=>{{
  if(!_frames.length) return;
  const frame=Math.floor(player.currentTime*_fps);
  const bucket=Math.floor(frame/_step)*_step;
  const idx=_fmap[bucket];
  if(idx===undefined||idx===_lastIdx) return;
  _lastIdx=idx; updatePanel(_frames[idx]);
}});

async function loadDetail(){{
  const data=await fetch('/api/video/'+VID).then(r=>r.json());
  _frames=data.frames; _fps=data.fps; _step=data.step;
  _frames.forEach((f,i)=>_fmap[f.frame]=i);
  player.src='/media/'+VID;
  document.getElementById('hdr').textContent=VID;
  document.getElementById('sub').textContent=
    `${{data.total_frames}}프레임 · step=${{data.step}} · ${{data.fps}}fps`;
  document.title=VID+' — 포커스';

  const gtWrap=document.getElementById('gt-tags');
  const gtAll=data.gt_all_tags||[];
  const gtDomain=data.gt_domain_tags||[];
  if(!gtAll.length){{
    gtWrap.innerHTML='<span class="gt-none">GT 태그 없음</span>';
  }}else{{
    gtWrap.innerHTML=gtAll.map(t=>{{
      const isDomain=gtDomain.includes(t);
      return `<span class="gt-chip${{isDomain?' domain':''}}">${{t}}</span>`;
    }}).join('');
  }}
  if(_frames.length){{updatePanel(_frames[0]);buildTimeline();}}
}}
loadDetail();
"""

_DETAIL_HTML = ("""<!DOCTYPE html>
<html lang="ko"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>포커스 상세</title>
<style>CSS</style></head><body>
<div class="wrap">
  <div class="topnav">
    <a href="/" class="back">&#8592; 목록</a>
    <div>
      <div class="kicker">Focus / DOF · Laplacian Variance</div>
      <h1 id="hdr" style="font-size:18px">&#8230;</h1>
      <p class="sub" id="sub"></p>
    </div>
  </div>
  <div class="player-wrap"><video id="player" controls preload="metadata"></video></div>
  <div id="stats-panel">
    <div class="panel-header">
      <span id="cur-label" class="badge">-</span>
      <span id="cur-time" class="sub">-</span>
    </div>
    <div class="stat-row">
      <span class="stat-label">global sharpness</span>
      <div class="bar-wrap"><div class="bar-fill" id="bar-global_s"></div></div>
      <span class="stat-val" id="val-global_s">-</span>
    </div>
    <div class="stat-row">
      <span class="stat-label">center sharpness</span>
      <div class="bar-wrap"><div class="bar-fill" id="bar-center_s"></div></div>
      <span class="stat-val" id="val-center_s">-</span>
    </div>
    <div class="stat-row">
      <span class="stat-label">bg sharpness</span>
      <div class="bar-wrap"><div class="bar-fill" id="bar-bg_s"></div></div>
      <span class="stat-val" id="val-bg_s">-</span>
    </div>
    <div class="stat-row">
      <span class="stat-label">center/bg ratio</span>
      <div class="bar-wrap"><div class="bar-fill" id="bar-cb_ratio"></div></div>
      <span class="stat-val" id="val-cb_ratio">-</span>
    </div>
    <div class="stat-row">
      <span class="stat-label">sharpness delta</span>
      <div class="bar-wrap"><div class="bar-fill" id="bar-delta"></div></div>
      <span class="stat-val" id="val-delta">-</span>
    </div>
    <div class="timeline-wrap">
      <div class="timeline-lbl">global_sharpness timeline</div>
      <svg id="timeline-svg"></svg>
      <div id="t-cursor"><div id="t-needle"></div></div>
    </div>
    <div class="gt-wrap">
      <div class="gt-lbl">Pikk 실제 태그 <span style="font-weight:400;color:var(--sub)">(포커스 관련 = 보라)</span></div>
      <div class="gt-tags" id="gt-tags"><span class="gt-none">로딩 중…</span></div>
    </div>
  </div>
</div>
<script>JS</script></body></html>""").replace("CSS", _CSS).replace("JS", _DETAIL_JS)


@app.get("/")
def index():
    return Response(_HOME_HTML, mimetype="text/html")


@app.get("/video/<video_id>")
def detail(video_id: str):
    return Response(_DETAIL_HTML, mimetype="text/html")


@app.get("/media/<video_id>")
def media(video_id: str):
    for rp in _BASE.glob(f"*/{video_id}/focus_results.json"):
        data = json.loads(rp.read_text(encoding="utf-8"))
        path = Path(data.get("video", ""))
        if path.exists():
            return send_file(path, mimetype="video/mp4", conditional=True)
    abort(404)


@app.get("/api/videos")
def api_videos():
    gt = _load_gt()
    result = []
    for rp in sorted(_BASE.glob("*/*/focus_results.json")):
        try:
            data = json.loads(rp.read_text(encoding="utf-8"))
        except Exception:
            continue
        frames  = data.get("frames", [])
        counts: dict[str, int] = {}
        for f in frames:
            lbl = f.get("label", "normal")
            counts[lbl] = counts.get(lbl, 0) + 1
        dominant = max(counts, key=counts.get) if counts else "normal"
        vid_id   = rp.parent.name
        gt_info  = gt.get(vid_id, {})
        all_tags = gt_info.get("all_tags", [])
        domain_tags = [t for t in all_tags if any(kw in t for kw in _FOCUS_KW)]
        result.append({
            "video_id":       vid_id,
            "technique":      rp.parent.parent.name,
            "total_frames":   len(frames),
            "fps":            data.get("fps", 0),
            "step":           data.get("step", 30),
            "dominant_label": dominant,
            "label_counts":   counts,
            "gt_domain_tags": domain_tags,
        })
    return jsonify(result)


@app.get("/api/video/<video_id>")
def api_video(video_id: str):
    for rp in _BASE.glob(f"*/{video_id}/focus_results.json"):
        data    = json.loads(rp.read_text(encoding="utf-8"))
        gt      = _load_gt()
        gt_info = gt.get(video_id, {})
        all_tags = gt_info.get("all_tags", [])
        domain_tags = [t for t in all_tags if any(kw in t for kw in _FOCUS_KW)]
        return jsonify({
            "video_id":      video_id,
            "fps":           data.get("fps", 0),
            "step":          data.get("step", 30),
            "total_frames":  data.get("total_frames", 0),
            "frames":        data.get("frames", []),
            "gt_all_tags":   all_tags,
            "gt_domain_tags": domain_tags,
        })
    return jsonify({"error": "not found"}), 404


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="포커스 결과 뷰어")
    parser.add_argument("--port", type=int, default=5005)
    args = parser.parse_args()
    print(f"뷰어 시작: http://localhost:{args.port}")
    app.run(host="0.0.0.0", port=args.port, debug=False)


if __name__ == "__main__":
    main()
