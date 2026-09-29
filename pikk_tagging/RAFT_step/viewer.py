"""RAFT_step 분석 결과 뷰어 (Flask, 포트 5002).

홈: 영상 목록 (step=5, smooth 적용)
상세: 영상 플레이어 + 실시간 label 배지 + stats 바

python -m pikk_tagging.RAFT_step.viewer
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

# ad_video_analysis 루트가 sys.path에 없을 때도 동작하도록 보장
_repo_root = Path(__file__).resolve().parents[2]
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

try:
    from flask import Flask, Response, jsonify, send_file, abort
except ImportError:
    raise SystemExit("pip install flask")

try:
    from pikk_tagging.RAFT_step.smooth import smooth_and_classify
except ImportError as e:
    raise SystemExit(f"smooth.py import 실패: {e}")

_STEP_BASE = Path(r"C:\Users\llm\workspace\outputs\pikk_output\RAFT_step_s5")
app = Flask(__name__)


def _results_path(video_id: str) -> Path:
    return _STEP_BASE / video_id / "step_results.json"


def _video_path(data: dict) -> Path | None:
    p = Path(data.get("video", ""))
    return p if p.exists() else None


_LABEL_COLORS = {
    "zoom_in":    ("#1baf7a", "#e6f7f1"),
    "zoom_out":   ("#8153c7", "#f0eafc"),
    "pan_right":  ("#2a78d6", "#e8f1fc"),
    "pan_left":   ("#2a78d6", "#e8f1fc"),
    "tilt_up":    ("#0093a7", "#e6f5f7"),
    "tilt_down":  ("#0093a7", "#e6f5f7"),
    "rotate_cw":  ("#c7920f", "#fdf3e0"),
    "rotate_ccw": ("#c7920f", "#fdf3e0"),
    "motion":     ("#5a6475", "#f0f2f5"),
    "static":     ("#9aa4b5", "#f7f8fa"),
}

_CSS = """
@import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/static/pretendard.css');
:root{
  --bg:#f7f8fa;--card:#fff;--ink:#1c2330;--sub:#5a6475;--line:#e3e7ee;
  --blue:#2a78d6;--blue-soft:#e8f1fc;--green:#1baf7a;
}
@media(prefers-color-scheme:dark){
  :root{--bg:#12151b;--card:#1b2029;--ink:#e8ecf3;--sub:#9aa4b5;--line:#2b3342;
    --blue-soft:#17293f;}
}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--bg);color:var(--ink);
  font-family:'Pretendard','Apple SD Gothic Neo','Noto Sans KR',sans-serif;
  font-size:14px;line-height:1.65}
.wrap{max-width:1100px;margin:0 auto;padding:28px 20px 72px}
.topnav{display:flex;align-items:center;gap:14px;margin-bottom:22px;
  padding-bottom:18px;border-bottom:1px solid var(--line)}
.kicker{font-size:11px;letter-spacing:.12em;color:var(--green);
  font-weight:700;text-transform:uppercase;margin-bottom:3px}
h1{font-size:21px;font-weight:700;letter-spacing:-.02em}
a.back{background:var(--card);border:1px solid var(--line);border-radius:8px;
  padding:6px 14px;color:var(--ink);text-decoration:none;font-size:13px}
a.back:hover{border-color:var(--blue);color:var(--blue)}
.sub{font-size:13px;color:var(--sub)}
.card{background:var(--card);border:1px solid var(--line);border-radius:14px;overflow:hidden}
table{width:100%;border-collapse:collapse}
th{padding:10px 12px;font-size:11px;color:var(--sub);font-weight:600;
  border-bottom:2px solid var(--line);text-align:left;
  white-space:nowrap;letter-spacing:.06em;text-transform:uppercase}
td{padding:8px 12px;border-bottom:1px solid var(--line);vertical-align:middle}
tr:last-child td{border-bottom:none}
tbody tr:hover td{background:var(--blue-soft);transition:background .1s}
.mono{font-family:monospace;font-size:12px}
.badge{display:inline-block;padding:3px 10px;border-radius:99px;
  font-size:12px;font-weight:700;letter-spacing:.04em}
.vtd{padding:4px 8px;width:172px}
.vthumb{width:160px;height:90px;background:#0b0c10;border-radius:9px;
  cursor:pointer;display:flex;align-items:center;justify-content:center;
  overflow:hidden;transition:opacity .15s}
.vthumb:hover{opacity:.8}
.play-ic{width:34px;height:34px;border-radius:50%;
  background:rgba(255,255,255,.16);display:flex;align-items:center;
  justify-content:center;color:#fff;font-size:14px}
video.mini{width:160px;border-radius:9px;display:block;background:#000}
.dist-wrap{display:flex;height:8px;border-radius:4px;overflow:hidden;gap:1px;min-width:140px}
.dist-seg{height:100%}
.player-wrap{background:#000;border-radius:14px;overflow:hidden;margin-bottom:14px}
.player-wrap video{width:100%;max-height:56vh;display:block}
#stats-panel{background:var(--card);border:1px solid var(--line);
  border-radius:14px;padding:18px 22px}
.panel-header{display:flex;align-items:center;gap:14px;margin-bottom:16px;flex-wrap:wrap}
#cur-label{font-size:22px;font-weight:800;letter-spacing:-.01em;
  padding:4px 16px;border-radius:10px;transition:background .12s,color .12s}
#spike-badge{display:none;font-size:11px;color:#eb6834;font-weight:700;
  border:1px solid #eb6834;border-radius:6px;padding:2px 8px}
.stat-row{display:grid;grid-template-columns:130px 1fr 90px;
  align-items:center;gap:12px;margin-bottom:10px}
.stat-row:last-child{margin-bottom:0}
.stat-label{font-size:11px;color:var(--sub);font-weight:600;
  text-transform:uppercase;letter-spacing:.06em}
.bar-wrap{position:relative;height:10px;background:var(--line);border-radius:5px}
.center-tick{position:absolute;left:50%;top:0;width:1px;height:100%;
  background:var(--sub);opacity:.35;pointer-events:none}
.bar-fill{position:absolute;top:0;height:100%;border-radius:5px;
  transition:left .08s,width .08s,background .08s}
.stat-val{font-family:monospace;font-size:12px;text-align:right;color:var(--ink)}
#lb{display:none;position:fixed;inset:0;background:rgba(0,0,0,.78);
  z-index:9999;align-items:center;justify-content:center}
#lb.show{display:flex}
#lb img{max-width:90vw;max-height:86vh;border-radius:10px}
#lb-close{position:absolute;top:18px;right:24px;color:#fff;font-size:28px;cursor:pointer}
#flow-thumb{width:96px;height:54px;object-fit:cover;border-radius:6px;
  cursor:zoom-in;border:1px solid var(--line);display:block}
.panel-body{display:flex;gap:20px;align-items:flex-start}
.panel-body-left{flex:1}
.panel-body-right{display:flex;flex-direction:column;gap:6px;align-items:flex-end}
"""

_LABEL_COLORS_JS = json.dumps(_LABEL_COLORS)

_HOME_JS = f"""
const COLORS = {_LABEL_COLORS_JS};
function fg(l){{ return (COLORS[l]||['#9aa4b5','#f0f2f5'])[0]; }}

function playThumb(el, vid){{
  const cell = el.parentElement; el.style.display='none';
  let v = cell.querySelector('video');
  if(!v){{ v=document.createElement('video'); v.className='mini'; v.controls=true; cell.appendChild(v); }}
  v.src='/media/'+vid; v.style.display='block'; v.play();
}}

function makeDist(counts, total){{
  const wrap=document.createElement('div'); wrap.className='dist-wrap';
  const ORDER=['zoom_in','zoom_out','pan_right','pan_left','tilt_up','tilt_down',
               'rotate_cw','rotate_ccw','motion','static'];
  for(const lbl of ORDER){{
    const cnt=counts[lbl]||0; if(!cnt) continue;
    const seg=document.createElement('div'); seg.className='dist-seg';
    seg.style.width=(cnt/total*100).toFixed(1)+'%';
    seg.style.background=fg(lbl);
    seg.title=lbl+': '+cnt;
    wrap.appendChild(seg);
  }}
  return wrap;
}}

async function loadList(){{
  const vids=await fetch('/api/videos').then(r=>r.json());
  document.getElementById('count').textContent='총 '+vids.length+'개';
  const tb=document.getElementById('tbody');
  vids.forEach(v=>{{
    const tr=document.createElement('tr'); tr.style.cursor='pointer';
    tr.innerHTML=
      `<td class="mono"><a href="/video/${{v.video_id}}" style="color:var(--blue);text-decoration:none">${{v.video_id}}</a></td>`+
      `<td class="vtd"><div class="vthumb" onclick="playThumb(this,'${{v.video_id}}');event.stopPropagation()"><span class="play-ic">&#9654;</span></div></td>`+
      `<td style="text-align:right">${{v.total_pairs}}</td>`+
      `<td class="mono">${{v.avg_mag.toFixed(1)}} px</td>`+
      `<td></td>`;
    if(v.label_counts) tr.cells[4].appendChild(makeDist(v.label_counts, v.total_pairs));
    tr.onclick=()=>location.href='/video/'+v.video_id;
    tb.appendChild(tr);
  }});
}}
loadList();
"""

_HOME_HTML = ("""<!DOCTYPE html>
<html lang="ko"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>RAFT_step 뷰어 (step=5)</title>
<style>CSS</style></head><body>
<div class="wrap">
  <div class="topnav">
    <div>
      <div class="kicker">RAFT Optical Flow · step=5 · Smoothed Labels</div>
      <h1>RAFT_step 뷰어</h1>
    </div>
    <span class="sub" id="count"></span>
  </div>
  <div class="card">
    <table><thead><tr>
      <th>영상 ID</th><th>영상</th><th>쌍 수</th>
      <th>avg mag</th><th>레이블 분포</th>
    </tr></thead><tbody id="tbody"></tbody></table>
  </div>
</div>
<script>JS</script></body></html>""").replace("CSS", _CSS).replace("JS", _HOME_JS)


_DETAIL_JS = f"""
const VID=location.pathname.split('/').pop();
const player=document.getElementById('player');
const COLORS={_LABEL_COLORS_JS};

let _pairs=[],_pairMap={{}},_fps=25,_step=5,_norms={{}},_lastIdx=-1;

const lb=document.getElementById('lb'),lbImg=document.getElementById('lb-img');
document.getElementById('lb-close').onclick=()=>lb.classList.remove('show');
lb.addEventListener('click',e=>{{if(e.target===lb)lb.classList.remove('show');}});
document.addEventListener('keydown',e=>{{if(e.key==='Escape')lb.classList.remove('show');}});

function updateSignedBar(id,value,maxAbs,posColor,negColor){{
  const el=document.getElementById('bar-'+id);
  const pct=Math.min(50,maxAbs>0?Math.abs(value)/maxAbs*50:0);
  if(value>=0){{el.style.left='50%';el.style.width=pct+'%';el.style.background=posColor;}}
  else{{el.style.left=(50-pct)+'%';el.style.width=pct+'%';el.style.background=negColor;}}
}}
function updateUnsignedBar(id,value,maxVal,color){{
  const el=document.getElementById('bar-'+id);
  const pct=Math.min(100,maxVal>0?value/maxVal*100:0);
  el.style.left='0';el.style.width=pct+'%';el.style.background=color;
}}

function updatePanel(pair){{
  if(!pair||!pair.stats) return;
  const s=pair.stats;
  const lbl=pair.label||'static';
  const [fg,bg]=COLORS[lbl]||['#9aa4b5','#f0f2f5'];

  const labelEl=document.getElementById('cur-label');
  labelEl.textContent=lbl;
  labelEl.style.color=fg;
  labelEl.style.background=bg;

  document.getElementById('cur-time').textContent=
    `frame ${{pair.frame_a}} → ${{pair.frame_b}}  (${{pair.time_a}}s → ${{pair.time_b}}s)`;
  document.getElementById('spike-badge').style.display=pair.is_spike?'inline':'none';

  updateUnsignedBar('mean_mag',s.mean_mag,_norms.mean_mag,'#2a78d6');
  document.getElementById('val-mean_mag').textContent=s.mean_mag.toFixed(2)+' px';
  updateSignedBar('zoom_score',s.zoom_score,_norms.zoom_score,'#1baf7a','#8153c7');
  document.getElementById('val-zoom_score').textContent=s.zoom_score.toFixed(4);
  updateSignedBar('pan_x',s.pan_x,_norms.pan_x,'#1baf7a','#0093a7');
  document.getElementById('val-pan_x').textContent=s.pan_x.toFixed(2)+' px';
  updateSignedBar('pan_y',s.pan_y,_norms.pan_y,'#eb6834','#0093a7');
  document.getElementById('val-pan_y').textContent=s.pan_y.toFixed(2)+' px';
  updateSignedBar('rotation_score',s.rotation_score,_norms.rotation_score,'#c7920f','#a06010');
  document.getElementById('val-rotation_score').textContent=s.rotation_score.toFixed(4);
  updateUnsignedBar('flow_var',s.flow_var,_norms.flow_var,'#9aa4b5');
  document.getElementById('val-flow_var').textContent=s.flow_var.toFixed(1);

  const thumb=document.getElementById('flow-thumb');
  if(pair.flow_viz){{
    const src='/flow/'+VID+'/'+pair.flow_viz;
    thumb.src=src; thumb.style.display='block';
    thumb.onclick=()=>{{lbImg.src=src;lb.classList.add('show');}};
  }}else{{thumb.style.display='none';}}
}}

player.addEventListener('timeupdate',()=>{{
  if(!_pairs.length) return;
  const frame=Math.floor(player.currentTime*_fps);
  const bucket=Math.floor(frame/_step)*_step;
  const idx=_pairMap[bucket];
  if(idx===undefined||idx===_lastIdx) return;
  _lastIdx=idx;
  updatePanel(_pairs[idx]);
}});

async function loadDetail(){{
  const data=await fetch('/api/video/'+VID).then(r=>r.json());
  _pairs=data.pairs; _fps=data.fps; _step=data.step;
  data.pairs.forEach((p,i)=>_pairMap[p.frame_a]=i);
  const s=data.pairs.filter(p=>p.stats).map(p=>p.stats);
  _norms={{
    mean_mag:       Math.max(...s.map(x=>x.mean_mag),1),
    zoom_score:     Math.max(...s.map(x=>Math.abs(x.zoom_score)),0.001),
    pan_x:          Math.max(...s.map(x=>Math.abs(x.pan_x)),1),
    pan_y:          Math.max(...s.map(x=>Math.abs(x.pan_y)),1),
    rotation_score: Math.max(...s.map(x=>Math.abs(x.rotation_score)),0.001),
    flow_var:       Math.max(...s.map(x=>x.flow_var),1),
  }};
  player.src='/media/'+VID;
  document.getElementById('hdr').textContent=VID;
  document.getElementById('sub').textContent=
    `${{data.total_pairs}}쌍 · step=${{data.step}} · ${{data.fps}}fps · ${{data.duration_sec}}s`;
  document.title=VID+' — RAFT_step';
  if(data.pairs.length) updatePanel(data.pairs[0]);
}}
loadDetail();
"""

_DETAIL_HTML = ("""<!DOCTYPE html>
<html lang="ko"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>RAFT_step 상세</title>
<style>CSS</style></head><body>
<div class="wrap">
  <div class="topnav">
    <a href="/" class="back">&#8592; 목록</a>
    <div>
      <div class="kicker">RAFT_step · Smoothed Classification</div>
      <h1 id="hdr" style="font-size:18px">&#8230;</h1>
      <p class="sub" id="sub"></p>
    </div>
  </div>

  <div class="player-wrap">
    <video id="player" controls preload="metadata"></video>
  </div>

  <div id="stats-panel">
    <div class="panel-header">
      <span id="cur-label" class="badge">-</span>
      <span id="cur-time" class="sub">-</span>
      <span id="spike-badge">SPIKE (보간값)</span>
    </div>
    <div class="panel-body">
      <div class="panel-body-left">
        <div class="stat-row">
          <span class="stat-label">mean mag</span>
          <div class="bar-wrap"><div class="bar-fill" id="bar-mean_mag"></div></div>
          <span class="stat-val" id="val-mean_mag">-</span>
        </div>
        <div class="stat-row">
          <span class="stat-label">zoom (+in/-out)</span>
          <div class="bar-wrap"><div class="center-tick"></div><div class="bar-fill" id="bar-zoom_score"></div></div>
          <span class="stat-val" id="val-zoom_score">-</span>
        </div>
        <div class="stat-row">
          <span class="stat-label">pan x (+R/-L)</span>
          <div class="bar-wrap"><div class="center-tick"></div><div class="bar-fill" id="bar-pan_x"></div></div>
          <span class="stat-val" id="val-pan_x">-</span>
        </div>
        <div class="stat-row">
          <span class="stat-label">pan y (+D/-U)</span>
          <div class="bar-wrap"><div class="center-tick"></div><div class="bar-fill" id="bar-pan_y"></div></div>
          <span class="stat-val" id="val-pan_y">-</span>
        </div>
        <div class="stat-row">
          <span class="stat-label">rotation (+CW/-CCW)</span>
          <div class="bar-wrap"><div class="center-tick"></div><div class="bar-fill" id="bar-rotation_score"></div></div>
          <span class="stat-val" id="val-rotation_score">-</span>
        </div>
        <div class="stat-row">
          <span class="stat-label">flow var</span>
          <div class="bar-wrap"><div class="bar-fill" id="bar-flow_var"></div></div>
          <span class="stat-val" id="val-flow_var">-</span>
        </div>
      </div>
      <div class="panel-body-right">
        <img id="flow-thumb" style="display:none">
      </div>
    </div>
  </div>
</div>
<div id="lb"><span id="lb-close">&times;</span><img id="lb-img"></div>
<script>JS</script></body></html>""").replace("CSS", _CSS).replace("JS", _DETAIL_JS)


# ── Routes ────────────────────────────────────────────────────────────────────
@app.get("/")
def index():
    return Response(_HOME_HTML, mimetype="text/html")


@app.get("/video/<video_id>")
def detail(video_id: str):
    return Response(_DETAIL_HTML, mimetype="text/html")


@app.get("/media/<video_id>")
def media(video_id: str):
    rp = _results_path(video_id)
    if not rp.exists():
        abort(404)
    data = json.loads(rp.read_text(encoding="utf-8"))
    path = _video_path(data)
    if path is None:
        abort(404)
    return send_file(path, mimetype="video/mp4", conditional=True)


@app.get("/flow/<video_id>/<filename>")
def flow_image(video_id: str, filename: str):
    p = _STEP_BASE / video_id / "flow_viz" / filename
    if not p.exists():
        abort(404)
    return send_file(p, mimetype="image/png")


@app.get("/api/videos")
def api_videos():
    result = []
    for rp in sorted(_STEP_BASE.glob("*/step_results.json")):
        try:
            data = json.loads(rp.read_text(encoding="utf-8"))
        except Exception:
            continue
        pairs = data.get("pairs", [])
        step = data.get("step", 5)
        try:
            rows = smooth_and_classify(pairs, step=step, min_frames=10)
        except Exception:
            rows = []
        mags = [p["stats"]["mean_mag"] for p in pairs if p.get("stats")]
        label_counts: dict[str, int] = {}
        for r in rows:
            lbl = r["label"]
            label_counts[lbl] = label_counts.get(lbl, 0) + 1
        result.append({
            "video_id":    rp.parent.name,
            "total_pairs": len(pairs),
            "fps":         data.get("fps", 0),
            "step":        step,
            "avg_mag":     round(sum(mags) / len(mags), 2) if mags else 0,
            "label_counts": label_counts,
        })
    return jsonify(result)


@app.get("/api/video/<video_id>")
def api_video(video_id: str):
    rp = _results_path(video_id)
    if not rp.exists():
        return jsonify({"error": "not found"}), 404
    data = json.loads(rp.read_text(encoding="utf-8"))
    pairs = data.get("pairs", [])
    step = data.get("step", 5)
    try:
        rows = smooth_and_classify(pairs, step=step, min_frames=10)
    except Exception:
        rows = [{**p, "label": "static", "is_spike": False} for p in pairs]
    last = rows[-1] if rows else {}
    return jsonify({
        "video_id":    video_id,
        "fps":         data.get("fps", 0),
        "step":        step,
        "total_pairs": len(rows),
        "duration_sec": round(last.get("time_b", 0), 1),
        "pairs":       rows,
    })


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="RAFT_step 분석 결과 뷰어")
    parser.add_argument("--port", type=int, default=5002)
    args = parser.parse_args()
    print(f"뷰어 시작: http://localhost:{args.port}")
    app.run(host="0.0.0.0", port=args.port, debug=False)


if __name__ == "__main__":
    main()
