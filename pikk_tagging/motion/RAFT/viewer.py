"""RAFT 분석 결과 뷰어 (Flask).

python -m pikk_tagging.RAFT.viewer
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

try:
    from flask import Flask, Response, jsonify, send_file, abort
except ImportError:
    raise SystemExit("pip install flask")

_RAFT_BASE = Path(r"C:\Users\llm\workspace\outputs\pikk_output\RAFT")

app = Flask(__name__)


def _summary_path(video_id: str) -> Path:
    return _RAFT_BASE / video_id / "motion_summary.json"


def _flow_image_path(video_id: str, filename: str) -> Path:
    return _RAFT_BASE / video_id / "flow_viz" / filename


def _video_path_from_summary(data: dict) -> Path | None:
    p = Path(data.get("video", ""))
    return p if p.exists() else None


def _flow_filename(shot: dict) -> str:
    """shot dict → flow viz 파일명 (새 단일쌍 포맷)."""
    return (f"shot_{shot['shot_idx']:02d}_flow_"
            f"{shot['frame_a']:05d}_{shot['frame_b']:05d}.png")


# ── CSS / JS 공유 ──────────────────────────────────────────────────────────────
_CSS = """
@import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/static/pretendard.css');
:root{
  --bg:#f7f8fa;--card:#fff;--ink:#1c2330;--sub:#5a6475;--line:#e3e7ee;
  --blue:#2a78d6;--blue-soft:#e8f1fc;--green:#1baf7a;--green-soft:#e4f6ee;
}
@media(prefers-color-scheme:dark){
  :root{--bg:#12151b;--card:#1b2029;--ink:#e8ecf3;--sub:#9aa4b5;--line:#2b3342;
    --blue-soft:#17293f;--green-soft:#143126;}
}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--bg);color:var(--ink);
  font-family:'Pretendard','Apple SD Gothic Neo','Noto Sans KR',sans-serif;
  font-size:14px;line-height:1.65}
.wrap{max-width:1200px;margin:0 auto;padding:28px 20px 72px}
.topnav{display:flex;align-items:center;gap:14px;margin-bottom:22px;
  padding-bottom:18px;border-bottom:1px solid var(--line)}
.kicker{font-size:11px;letter-spacing:.12em;color:var(--green);
  font-weight:700;text-transform:uppercase;margin-bottom:3px}
h1{font-size:21px;font-weight:700;letter-spacing:-.02em}
a.back{background:var(--card);border:1px solid var(--line);border-radius:8px;
  padding:6px 14px;color:var(--ink);text-decoration:none;font-size:13px;
  transition:border-color .15s}
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
.badge{display:inline-block;padding:2px 8px;border-radius:99px;
  font-size:11px;font-weight:600;margin:1px;white-space:nowrap}
/* video thumb */
.vtd{padding:4px 8px;width:172px}
.vthumb{width:160px;height:90px;background:#0b0c10;border-radius:9px;
  cursor:pointer;display:flex;align-items:center;justify-content:center;
  overflow:hidden;transition:opacity .15s}
.vthumb:hover{opacity:.8}
.play-ic{width:34px;height:34px;border-radius:50%;
  background:rgba(255,255,255,.16);display:flex;align-items:center;
  justify-content:center;color:#fff;font-size:14px}
video.mini{width:160px;border-radius:9px;display:block;background:#000}
/* detail layout */
.detail-layout{display:grid;grid-template-columns:minmax(260px,2fr) minmax(380px,3fr);
  gap:16px;align-items:start}
.player-col{position:sticky;top:16px}
.player-wrap{background:#000;border-radius:14px;overflow:hidden;margin-bottom:10px}
.player-wrap video{width:100%;display:block}
.shots-col{overflow-y:auto;max-height:calc(100vh - 100px);border-radius:14px}
.splay{width:28px;height:28px;border-radius:50%;border:1px solid var(--line);
  background:var(--card);cursor:pointer;font-size:11px;color:var(--ink);
  display:inline-flex;align-items:center;justify-content:center;transition:all .15s}
.splay:hover,.splay.on{background:var(--blue);color:#fff;border-color:var(--blue)}
#stbody tr.playing td{background:rgba(42,120,214,.09)!important;transition:background .2s}
/* flow viz thumb */
.fthumb{width:72px;height:40px;object-fit:cover;border-radius:5px;cursor:zoom-in;
  display:block;border:1px solid var(--line)}
/* lightbox */
#lb{display:none;position:fixed;inset:0;background:rgba(0,0,0,.78);
  z-index:9999;align-items:center;justify-content:center}
#lb.show{display:flex}
#lb img{max-width:90vw;max-height:86vh;border-radius:10px;box-shadow:0 8px 40px #0009}
#lb-close{position:absolute;top:18px;right:24px;color:#fff;font-size:28px;
  cursor:pointer;line-height:1}
/* mag bar */
.mag-bar{display:inline-block;height:6px;border-radius:3px;
  background:var(--blue);min-width:2px;vertical-align:middle;margin-left:4px}
"""

_BADGE_JS = """
const C={zoom_in:'#2a78d6',zoom_out:'#8153c7',
  pan:'#1baf7a',pan_left:'#1baf7a',pan_right:'#1baf7a',
  pan_up:'#0093a7',pan_down:'#0093a7',tilt:'#0093a7',
  handheld:'#eb6834',static:'#6c757d',unknown:'#ced4da',
  rotate:'#c7920f',cut:'#dc3545',too_short:'#e9ecef',error:'#dc3545'};
const LIGHT=new Set(['unknown','too_short','static','tilt','pan_up','pan_down']);
function badge(l,cnt){
  const bg=C[l]||'#adb5bd',tc=LIGHT.has(l)?'#333':'#fff';
  const label=cnt>1?`${l} ×${cnt}`:l;
  return `<span class="badge" style="background:${bg};color:${tc}">${label}</span>`;
}
"""

# ── Home ──────────────────────────────────────────────────────────────────────
_HOME_JS = _BADGE_JS + """
function playThumb(el,vid){
  const cell=el.parentElement;el.style.display='none';
  let v=cell.querySelector('video');
  if(!v){v=document.createElement('video');v.className='mini';v.controls=true;cell.appendChild(v);}
  v.src='/media/'+vid;v.style.display='block';v.play();
}
async function loadList(){
  const vids=await fetch('/api/videos').then(r=>r.json());
  document.getElementById('count').textContent='총 '+vids.length+'개';
  const tb=document.getElementById('tbody');
  vids.forEach(v=>{
    const tr=document.createElement('tr');
    tr.style.cursor='pointer';
    const motions=Object.entries(v.motion_counts)
      .sort((a,b)=>b[1]-a[1]).map(([l,c])=>badge(l,c)).join('');
    tr.innerHTML=
      `<td class="mono"><a href="/video/${v.video_id}" style="color:var(--blue);text-decoration:none">${v.video_id}</a></td>`+
      `<td class="vtd"><div class="vthumb" onclick="playThumb(this,'${v.video_id}');event.stopPropagation()"><span class="play-ic">&#9654;</span></div></td>`+
      `<td style="text-align:right">${v.n_shots}</td>`+
      `<td>${motions}</td>`+
      `<td class="sub">${v.fps} fps &nbsp; ${v.duration_sec}s</td>`;
    tr.onclick=()=>location.href='/video/'+v.video_id;
    tb.appendChild(tr);
  });
}
loadList();
"""

_HOME_HTML = ("""<!DOCTYPE html>
<html lang="ko"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>RAFT 모션 뷰어</title>
<style>PLACEHOLDER_CSS</style>
</head><body>
<div class="wrap">
  <div class="topnav">
    <div>
      <div class="kicker">RAFT Optical Flow &middot; 카메라 모션 분석</div>
      <h1>RAFT 분석 결과 뷰어</h1>
    </div>
    <span class="sub" id="count"></span>
  </div>
  <div class="card">
    <table>
      <thead><tr>
        <th>영상 ID</th><th>영상</th><th>샷 수</th><th>모션 분포</th><th>정보</th>
      </tr></thead>
      <tbody id="tbody"></tbody>
    </table>
  </div>
</div>
<script>PLACEHOLDER_JS</script>
</body></html>""").replace("PLACEHOLDER_CSS", _CSS).replace("PLACEHOLDER_JS", _HOME_JS)

# ── Detail ────────────────────────────────────────────────────────────────────
_DETAIL_JS = _BADGE_JS + """
const VID=location.pathname.split('/').pop();
const player=document.getElementById('player');
let _stopAt=null,_checkFn=null,_activeBtn=null,_shots=[];
let _lastHlIdx=-1;

function playShotAt(btn,start,end){
  if(_checkFn)player.removeEventListener('timeupdate',_checkFn);
  if(_activeBtn)_activeBtn.classList.remove('on');
  _activeBtn=btn;btn.classList.add('on');
  _stopAt=end;player.currentTime=start;player.play();
  _checkFn=()=>{
    if(player.currentTime>=_stopAt){
      player.pause();player.removeEventListener('timeupdate',_checkFn);
      _checkFn=null;
      if(_activeBtn){_activeBtn.classList.remove('on');_activeBtn=null;}
    }
  };
  player.addEventListener('timeupdate',_checkFn);
}

player.addEventListener('timeupdate',()=>{
  if(!_shots.length)return;
  const t=player.currentTime;
  const idx=_shots.findIndex(s=>t>=s.start_sec&&t<s.end_sec);
  if(idx===_lastHlIdx)return;
  _lastHlIdx=idx;
  const rows=document.querySelectorAll('#stbody tr');
  rows.forEach((r,i)=>i===idx?r.classList.add('playing'):r.classList.remove('playing'));
  if(idx>=0&&!player.paused)
    rows[idx]&&rows[idx].scrollIntoView({block:'nearest',behavior:'smooth'});
});

// lightbox
const lb=document.getElementById('lb');
const lbImg=document.getElementById('lb-img');
document.getElementById('lb-close').onclick=()=>lb.classList.remove('show');
lb.addEventListener('click',e=>{if(e.target===lb)lb.classList.remove('show');});
document.addEventListener('keydown',e=>{if(e.key==='Escape')lb.classList.remove('show');});
function showFlow(src){lbImg.src=src;lb.classList.add('show');}

async function loadDetail(){
  const data=await fetch('/api/video/'+VID).then(r=>r.json());
  _shots=data.shots;
  player.src='/media/'+VID;
  document.getElementById('hdr').textContent=VID;
  document.getElementById('sub').textContent=
    data.n_shots+'개 샷 · '+data.fps+' fps · '+(data.duration_sec||'?')+'s';
  document.title=VID+' — RAFT 뷰어';
  const tb=document.getElementById('stbody');
  const maxMag=Math.max(...data.shots.filter(s=>s.stats).map(s=>s.stats.mean_mag),1);
  data.shots.forEach(s=>{
    const tr=document.createElement('tr');
    const b=badge(s.motion_type,1);
    const mag=s.stats?s.stats.mean_mag.toFixed(1):'-';
    const barW=s.stats?Math.round(s.stats.mean_mag/maxMag*60):0;
    const magCell=s.stats
      ?`${mag}px<span class="mag-bar" style="width:${barW}px"></span>`
      :`<span class="sub">-</span>`;
    const flowSrc=s.flow_viz?`/flow/${VID}/${s.flow_viz}`:'';
    const flowCell=flowSrc
      ?`<img class="fthumb" src="${flowSrc}" onclick="showFlow('${flowSrc}')" title="flow 시각화">`
      :`<span class="sub">-</span>`;
    tr.innerHTML=
      `<td class="sub">${s.shot_idx+1}</td>`+
      `<td style="padding:4px 8px"><button class="splay" onclick="playShotAt(this,${s.start_sec},${s.end_sec})">&#9654;</button></td>`+
      `<td class="sub mono">${s.start_sec}~${s.end_sec}s</td>`+
      `<td class="sub">${s.duration_sec}s</td>`+
      `<td>${b}</td>`+
      `<td class="mono" style="white-space:nowrap">${magCell}</td>`+
      `<td>${flowCell}</td>`;
    tb.appendChild(tr);
  });
}
loadDetail();
"""

_DETAIL_HTML = ("""<!DOCTYPE html>
<html lang="ko"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>RAFT 샷 분석</title>
<style>PLACEHOLDER_CSS</style>
</head><body>
<div class="wrap">
  <div class="topnav">
    <a href="/" class="back">&#8592; 목록</a>
    <div>
      <div class="kicker">RAFT 분석</div>
      <h1 id="hdr" style="font-size:18px">&#8230;</h1>
      <p class="sub" id="sub"></p>
    </div>
  </div>
  <div class="detail-layout">
    <div class="player-col">
      <div class="player-wrap">
        <video id="player" controls preload="metadata"></video>
      </div>
    </div>
    <div class="shots-col card">
      <table>
        <thead><tr>
          <th>#</th><th>▷</th><th>구간</th><th>길이</th>
          <th>모션</th><th>이동량</th><th>Flow</th>
        </tr></thead>
        <tbody id="stbody"></tbody>
      </table>
    </div>
  </div>
</div>
<div id="lb"><span id="lb-close">&times;</span><img id="lb-img"></div>
<script>PLACEHOLDER_JS</script>
</body></html>""").replace("PLACEHOLDER_CSS", _CSS).replace("PLACEHOLDER_JS", _DETAIL_JS)


# ── Routes ────────────────────────────────────────────────────────────────────
@app.get("/")
def index() -> Response:
    return Response(_HOME_HTML, mimetype="text/html")


@app.get("/video/<video_id>")
def detail(video_id: str) -> Response:
    return Response(_DETAIL_HTML, mimetype="text/html")


@app.get("/media/<video_id>")
def media(video_id: str):
    sp = _summary_path(video_id)
    if not sp.exists():
        abort(404)
    try:
        data = json.loads(sp.read_text(encoding="utf-8"))
    except Exception:
        abort(404)
    path = _video_path_from_summary(data)
    if path is None:
        abort(404)
    return send_file(path, mimetype="video/mp4", conditional=True)


@app.get("/flow/<video_id>/<filename>")
def flow_image(video_id: str, filename: str):
    p = _flow_image_path(video_id, filename)
    if not p.exists():
        abort(404)
    return send_file(p, mimetype="image/png")


@app.get("/api/videos")
def api_videos():
    result = []
    for sp in sorted(_RAFT_BASE.glob("*/motion_summary.json")):
        try:
            data = json.loads(sp.read_text(encoding="utf-8"))
        except Exception:
            continue
        shots = data.get("shots", [])
        counts: Counter = Counter(
            s["motion_type"] for s in shots
            if s.get("motion_type") not in ("too_short", "read_error", "error", "unknown")
        )
        last_shot = shots[-1] if shots else {}
        duration = last_shot.get("end_sec", 0)
        result.append({
            "video_id":     sp.parent.name,
            "n_shots":      len(shots),
            "fps":          data.get("fps", 0),
            "duration_sec": duration,
            "motion_counts": dict(counts.most_common()),
        })
    return jsonify(result)


@app.get("/api/video/<video_id>")
def api_video(video_id: str):
    sp = _summary_path(video_id)
    if not sp.exists():
        return jsonify({"error": "not found"}), 404
    try:
        data = json.loads(sp.read_text(encoding="utf-8"))
    except Exception:
        return jsonify({"error": "parse error"}), 500

    shots = data.get("shots", [])
    last_shot = shots[-1] if shots else {}

    # flow_viz 파일명 주입 (stats가 있는 샷만)
    viz_dir = _RAFT_BASE / video_id / "flow_viz"
    for s in shots:
        if s.get("stats"):
            fname = _flow_filename(s)
            s["flow_viz"] = fname if (viz_dir / fname).exists() else None
        else:
            s["flow_viz"] = None

    return jsonify({
        "video_id":    video_id,
        "fps":         data.get("fps", 0),
        "n_shots":     len(shots),
        "duration_sec": last_shot.get("end_sec", 0),
        "shots":       shots,
    })


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="RAFT 분석 결과 뷰어")
    parser.add_argument("--port", type=int, default=5001)
    args = parser.parse_args()
    print(f"뷰어 시작: http://localhost:{args.port}")
    app.run(host="0.0.0.0", port=args.port, debug=False)


if __name__ == "__main__":
    main()
