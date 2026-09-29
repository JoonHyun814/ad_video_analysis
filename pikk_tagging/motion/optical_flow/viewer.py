"""광고 영상 모션 분석 결과 뷰어 (Flask).

python -m pikk_tagging.motion.optical_flow.viewer
"""
from __future__ import annotations

import json
from pathlib import Path

try:
    from flask import Flask, Response, jsonify, send_file, abort
except ImportError:
    raise SystemExit("pip install flask")

_OUT_BASE = Path(r"C:\Users\llm\workspace\outputs\pikk_output\videos")
_VIDEO_BASE = Path(r"C:\Users\llm\workspace\outputs\pikk_output\motion_test")
app = Flask(__name__)


def _find_video_path(video_id: str) -> Path | None:
    d = _VIDEO_BASE / video_id
    if not d.exists():
        return None
    for ext in (".mp4", ".webm", ".mkv"):
        p = d / f"{video_id}{ext}"
        if p.exists():
            return p
    for ext in (".mp4", ".webm", ".mkv"):
        hits = list(d.rglob(f"*{ext}"))
        if hits:
            return hits[0]
    return None


# ──────────────────────────────────────────────────────────────
#  Shared CSS
# ──────────────────────────────────────────────────────────────
_CSS = """
@import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/static/pretendard.css');
:root{
  --bg:#f7f8fa;--card:#fff;--ink:#1c2330;--sub:#5a6475;--line:#e3e7ee;
  --blue:#2a78d6;--blue-soft:#e8f1fc;
  --green:#1baf7a;--green-soft:#e4f6ee;
  --orange:#eb6834;--purple:#8153c7;
}
@media(prefers-color-scheme:dark){
  :root{
    --bg:#12151b;--card:#1b2029;--ink:#e8ecf3;--sub:#9aa4b5;--line:#2b3342;
    --blue-soft:#17293f;--green-soft:#143126;
  }
}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--bg);color:var(--ink);
  font-family:'Pretendard','Apple SD Gothic Neo','Noto Sans KR',sans-serif;
  font-size:14px;line-height:1.65}
.wrap{max-width:1140px;margin:0 auto;padding:28px 20px 72px}
.topnav{display:flex;align-items:center;gap:14px;margin-bottom:22px;
  padding-bottom:18px;border-bottom:1px solid var(--line)}
.kicker{font-size:11px;letter-spacing:.12em;color:var(--green);
  font-weight:700;text-transform:uppercase;margin-bottom:3px}
h1{font-size:21px;font-weight:700;letter-spacing:-.02em}
a.back{background:var(--card);border:1px solid var(--line);border-radius:8px;
  padding:6px 14px;color:var(--ink);text-decoration:none;font-size:13px;
  transition:border-color .15s,color .15s}
a.back:hover{border-color:var(--blue);color:var(--blue)}
.sub{font-size:13px;color:var(--sub)}
.card{background:var(--card);border:1px solid var(--line);border-radius:14px;overflow:hidden}
table{width:100%;border-collapse:collapse}
th{padding:10px 12px;font-size:11px;color:var(--sub);font-weight:600;
  border-bottom:2px solid var(--line);text-align:left;
  white-space:nowrap;letter-spacing:.06em;text-transform:uppercase}
td{padding:9px 12px;border-bottom:1px solid var(--line);vertical-align:middle}
tr:last-child td{border-bottom:none}
tbody tr:hover td{background:var(--blue-soft);transition:background .1s}
.gt-row td{background:var(--green-soft)}
.mono{font-family:monospace;font-size:12px}
.badge{display:inline-block;padding:2px 8px;border-radius:99px;
  font-size:11px;font-weight:600;margin:1px;white-space:nowrap}
.match-ok{outline:2px solid var(--green);outline-offset:1px}
.match-fail{outline:2px solid #dc3545;outline-offset:1px}
.star{color:#c7920f}
/* video thumb in list */
.vtd{padding:4px 8px;width:172px}
.vthumb{width:160px;height:90px;background:#0b0c10;border-radius:9px;
  cursor:pointer;display:flex;align-items:center;justify-content:center;
  overflow:hidden;transition:opacity .15s}
.vthumb:hover{opacity:.8}
.play-ic{width:34px;height:34px;border-radius:50%;
  background:rgba(255,255,255,.16);display:flex;align-items:center;
  justify-content:center;color:#fff;font-size:14px}
video.mini{width:160px;border-radius:9px;display:block;background:#000}
/* detail player */
.player-wrap{background:#000;border-radius:14px;overflow:hidden;margin-bottom:16px}
.player-wrap video{width:100%;max-height:460px;display:block}
/* shot play btn */
.splay{width:28px;height:28px;border-radius:50%;border:1px solid var(--line);
  background:var(--card);cursor:pointer;font-size:11px;color:var(--ink);
  display:inline-flex;align-items:center;justify-content:center;
  transition:all .15s;flex-shrink:0}
.splay:hover,.splay.on{background:var(--blue);color:#fff;border-color:var(--blue)}
/* detail two-column layout */
.detail-layout{display:grid;grid-template-columns:minmax(260px,2fr) minmax(380px,3fr);
  gap:16px;align-items:start}
.player-col{position:sticky;top:16px}
.player-wrap{background:#000;border-radius:14px;overflow:hidden}
.player-wrap video{width:100%;display:block}
.shots-col{overflow-y:auto;max-height:calc(100vh - 100px);border-radius:14px}
#stbody tr.playing td{background:rgba(42,120,214,.09)!important;transition:background .2s}
"""

# ──────────────────────────────────────────────────────────────
#  Shared badge JS (no Python f-string — raw JS with ${})
# ──────────────────────────────────────────────────────────────
_BADGE_JS = """
const C={zoom_in:'#2a78d6',zoom_out:'#8153c7',pan:'#1baf7a',tilt:'#0093a7',
  handheld:'#eb6834',static:'#6c757d',unknown:'#ced4da',rotate:'#c7920f',
  cut:'#dc3545',too_short:'#e9ecef'};
const LIGHT=new Set(['unknown','too_short','tilt']);
function badge(l){
  const bg=C[l]||'#adb5bd',tc=LIGHT.has(l)?'#333':'#fff';
  return `<span class="badge" style="background:${bg};color:${tc}">${l}</span>`;
}
function badgeMatch(l,gts){
  const skip=['unknown','cut','too_short',''];
  if(skip.includes(l))return badge(l);
  const ok=gts.some(g=>g===l||(g==='pan'&&l.startsWith('pan')));
  return badge(l).replace('class="badge"','class="badge '+(ok?'match-ok':'match-fail')+'"');
}
"""

# ──────────────────────────────────────────────────────────────
#  Home page
# ──────────────────────────────────────────────────────────────
_HOME_JS = _BADGE_JS + """
function playThumb(el,vid){
  const cell=el.parentElement;
  el.style.display='none';
  let v=cell.querySelector('video');
  if(!v){v=document.createElement('video');v.className='mini';v.controls=true;cell.appendChild(v);}
  v.src=`/media/${vid}`;
  v.style.display='block';
  v.play();
}
async function loadList(){
  const vids=await fetch('/api/videos').then(r=>r.json());
  document.getElementById('count').textContent='총 '+vids.length+'개';
  const tb=document.getElementById('tbody');
  vids.forEach(v=>{
    const tr=document.createElement('tr');
    tr.style.cursor='pointer';
    const gt=v.gt_labels.map(badge).join('');
    const osh=(v.dominant.osh||[]).map(l=>badgeMatch(l,v.gt_labels)).join('');
    const fb=(v.dominant.fb||[]).map(l=>badgeMatch(l,v.gt_labels)).join('');
    const lk=(v.dominant.lk||[]).map(l=>badgeMatch(l,v.gt_labels)).join('');
    tr.innerHTML=
      `<td class="mono">${v.video_id}</td>`+
      `<td class="vtd"><div class="vthumb" onclick="playThumb(this,'${v.video_id}');event.stopPropagation()"><span class="play-ic">&#9654;</span></div></td>`+
      `<td>${gt}</td><td>${osh}</td><td>${fb}</td><td>${lk}</td><td>${v.shot_count}</td>`;
    tr.onclick=()=>location.href='/video/'+v.video_id;
    tb.appendChild(tr);
  });
}
loadList();
"""

_HOME_HTML = ("""<!DOCTYPE html>
<html lang="ko"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>모션 분석 뷰어</title>
<style>PLACEHOLDER_CSS</style>
</head><body>
<div class="wrap">
  <div class="topnav">
    <div>
      <div class="kicker">Motion Analysis &middot; 광고 영상 카메라 기법</div>
      <h1>모션 분석 뷰어</h1>
    </div>
    <span class="sub" id="count"></span>
  </div>
  <div class="card">
    <table>
      <thead><tr>
        <th>영상 ID</th><th>영상</th><th>GT</th>
        <th>OSH</th><th>Farneback</th><th>LK</th><th>샷수</th>
      </tr></thead>
      <tbody id="tbody"></tbody>
    </table>
  </div>
</div>
<script>PLACEHOLDER_JS</script>
</body></html>""").replace("PLACEHOLDER_CSS", _CSS).replace("PLACEHOLDER_JS", _HOME_JS)

# ──────────────────────────────────────────────────────────────
#  Detail page
# ──────────────────────────────────────────────────────────────
_DETAIL_JS = _BADGE_JS + """
const VID=location.pathname.split('/').pop();
const player=document.getElementById('player');
let _stopAt=null,_checkFn=null,_activeBtn=null;
let _shots=[],_lastHlIdx=-1;

function playShotAt(btn,start,end){
  if(_checkFn)player.removeEventListener('timeupdate',_checkFn);
  if(_activeBtn)_activeBtn.classList.remove('on');
  _activeBtn=btn; btn.classList.add('on');
  _stopAt=end;
  player.currentTime=start;
  player.play();
  _checkFn=()=>{
    if(player.currentTime>=_stopAt){
      player.pause();
      player.removeEventListener('timeupdate',_checkFn);
      _checkFn=null;
      if(_activeBtn){_activeBtn.classList.remove('on');_activeBtn=null;}
    }
  };
  player.addEventListener('timeupdate',_checkFn);
}

player.addEventListener('timeupdate',()=>{
  if(!_shots.length)return;
  const t=player.currentTime;
  const idx=_shots.findIndex(s=>t>=s.start_sec&&t<=s.end_sec);
  if(idx===_lastHlIdx)return;
  _lastHlIdx=idx;
  const rows=document.querySelectorAll('#stbody tr');
  rows.forEach((r,i)=>i===idx?r.classList.add('playing'):r.classList.remove('playing'));
  if(idx>=0&&!player.paused)
    rows[idx]&&rows[idx].scrollIntoView({block:'nearest',behavior:'smooth'});
});

async function loadDetail(){
  const data=await fetch('/api/video/'+VID).then(r=>r.json());
  _shots=data.shots;
  player.src='/media/'+VID;
  const gtB=data.gt_labels.map(badge).join(' ');
  document.getElementById('hdr').innerHTML=
    `<code style="font-size:15px;font-weight:600">${VID}</code>&nbsp;${gtB}`+
    `&nbsp;<span class="sub">ts=${data.gt_timestamp_sec}s &nbsp;&middot;&nbsp; ${data.duration_sec}s</span>`;
  document.title=VID+' — 모션 뷰어';
  const tb=document.getElementById('stbody');
  data.shots.forEach(s=>{
    const tr=document.createElement('tr');
    if(s.is_gt_shot)tr.className='gt-row';
    const star=s.is_gt_shot?'<span class="star"> &#9733;</span>':'';
    const osh=badgeMatch(s.osh,data.gt_labels);
    const fb=badgeMatch(s.fb,data.gt_labels);
    const lk=badgeMatch(s.lk,data.gt_labels);
    tr.innerHTML=
      `<td>${s.shot_idx+1}${star}</td>`+
      `<td style="padding:5px 8px"><button class="splay" onclick="playShotAt(this,${s.start_sec},${s.end_sec})">&#9654;</button></td>`+
      `<td class="sub mono">${s.start_sec}~${s.end_sec}s</td>`+
      `<td class="sub">${s.duration_sec}s</td>`+
      `<td>${osh}</td><td>${fb}</td><td>${lk}</td>`;
    tb.appendChild(tr);
  });
}
loadDetail();
"""

_DETAIL_HTML = ("""<!DOCTYPE html>
<html lang="ko"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>샷 분석</title>
<style>PLACEHOLDER_CSS</style>
</head><body>
<div class="wrap">
  <div class="topnav">
    <a href="/" class="back">&#8592; 목록으로</a>
    <div id="hdr"><span class="sub">불러오는 중&#8230;</span></div>
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
          <th>#</th><th>영상</th><th>구간</th><th>길이</th>
          <th>OSH</th><th>Farneback</th><th>LK</th>
        </tr></thead>
        <tbody id="stbody"></tbody>
      </table>
    </div>
  </div>
</div>
<script>PLACEHOLDER_JS</script>
</body></html>""").replace("PLACEHOLDER_CSS", _CSS).replace("PLACEHOLDER_JS", _DETAIL_JS)


# ──────────────────────────────────────────────────────────────
#  Routes
# ──────────────────────────────────────────────────────────────
@app.get("/")
def index() -> Response:
    return Response(_HOME_HTML, mimetype="text/html")


@app.get("/video/<video_id>")
def detail(video_id: str) -> Response:
    return Response(_DETAIL_HTML, mimetype="text/html")


@app.get("/media/<video_id>")
def media(video_id: str):
    path = _find_video_path(video_id)
    if path is None:
        abort(404)
    return send_file(path, mimetype="video/mp4", conditional=True)


_NOISE = {"too_short", "cut", "unknown", ""}


def _unique_tags(shots: list, method: str) -> list[str]:
    seen: list[str] = []
    for s in shots:
        t = s.get(method, "")
        if t not in _NOISE and t not in seen:
            seen.append(t)
    return seen


@app.get("/api/videos")
def api_videos():
    videos = []
    for json_path in sorted(_OUT_BASE.glob("*/analysis.json")):
        try:
            data = json.loads(json_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        shots = data.get("shots", [])
        videos.append({
            "video_id":   data["video_id"],
            "gt_labels":  data.get("gt_labels", []),
            "dominant": {
                "osh": _unique_tags(shots, "osh"),
                "fb":  _unique_tags(shots, "fb"),
                "lk":  _unique_tags(shots, "lk"),
            },
            "shot_count": len(shots),
            "duration_sec": data.get("duration_sec", 0),
        })
    return jsonify(videos)


@app.get("/api/video/<video_id>")
def api_video(video_id: str):
    path = _OUT_BASE / video_id / "analysis.json"
    if not path.exists():
        return jsonify({"error": "not found"}), 404
    return jsonify(json.loads(path.read_text(encoding="utf-8")))


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="분석 결과 뷰어")
    parser.add_argument("--port", type=int, default=5000)
    args = parser.parse_args()
    print(f"뷰어 시작: http://localhost:{args.port}")
    app.run(host="0.0.0.0", port=args.port, debug=False)


if __name__ == "__main__":
    main()
