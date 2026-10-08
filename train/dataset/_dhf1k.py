"""DHF1K 데이터셋 시각화 패널 — saliency map + fixation map (annotation.rar 직접 읽기)."""

import io
import threading
import tkinter as tk
from pathlib import Path
from tkinter import ttk
from typing import Optional

import rarfile
from PIL import Image, ImageTk

_SPLITS = {"Train": (1, 600), "Val": (601, 700), "Test": (701, 1000)}
_THUMB = (320, 240)


def _split_of(vid_int: int) -> str:
    if vid_int <= 600:
        return "Train"
    if vid_int <= 700:
        return "Val"
    return "Test"


class DHF1KPanel(ttk.Frame):
    def __init__(self, parent: tk.Widget, dataset_path: Path) -> None:
        super().__init__(parent)
        self._path = dataset_path
        self._rar: Optional[rarfile.RarFile] = None
        self._all_videos: list[str] = []
        self._frames: list[str] = []
        self._frame_idx = 0
        self._img_refs: list = []
        self._build_ui()
        threading.Thread(target=self._load_rar, daemon=True).start()

    # ── UI 구성 ────────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        self._status = tk.StringVar(value="annotation.rar 인덱싱 중…")
        paned = ttk.PanedWindow(self, orient="horizontal")
        paned.pack(fill="both", expand=True)

        left = ttk.Frame(paned, width=180)
        paned.add(left, weight=0)
        ttk.Label(left, text="Split 필터").pack(anchor="w", padx=4, pady=(6, 2))
        self._split_var = tk.StringVar(value="All")
        for s in ("All", "Train", "Val", "Test"):
            ttk.Radiobutton(left, text=s, value=s, variable=self._split_var,
                            command=self._refresh_list).pack(anchor="w", padx=12)
        self._listbox = tk.Listbox(left, activestyle="dotbox", font=("Consolas", 9))
        sb = ttk.Scrollbar(left, command=self._listbox.yview)
        self._listbox.config(yscrollcommand=sb.set)
        self._listbox.pack(side="left", fill="both", expand=True, padx=(4, 0), pady=4)
        sb.pack(side="left", fill="y", pady=4)
        self._listbox.bind("<<ListboxSelect>>", self._on_video_select)
        ttk.Label(left, textvariable=self._status, wraplength=170).pack(padx=4, pady=4)

        right = ttk.Frame(paned)
        paned.add(right, weight=1)
        self._vid_label = ttk.Label(right, text="← 영상을 선택하세요", font=("", 10, "bold"))
        self._vid_label.pack(anchor="w", padx=8, pady=6)

        img_row = ttk.Frame(right)
        img_row.pack(fill="both", expand=True, padx=6)
        sal_col = ttk.Frame(img_row)
        sal_col.pack(side="left", padx=(0, 8))
        ttk.Label(sal_col, text="Saliency Map").pack()
        self._canvas_sal = tk.Canvas(sal_col, bg="#1a1a1a", width=_THUMB[0], height=_THUMB[1])
        self._canvas_sal.pack()

        fix_col = ttk.Frame(img_row)
        fix_col.pack(side="left")
        ttk.Label(fix_col, text="Fixation Map").pack()
        self._canvas_fix = tk.Canvas(fix_col, bg="#1a1a1a", width=_THUMB[0], height=_THUMB[1])
        self._canvas_fix.pack()

        nav = ttk.Frame(right)
        nav.pack(fill="x", padx=8, pady=6)
        ttk.Button(nav, text="◀", width=3, command=lambda: self._step(-1)).pack(side="left")
        self._frame_var = tk.IntVar(value=0)
        self._slider = ttk.Scale(nav, orient="horizontal", variable=self._frame_var,
                                 command=self._on_slider)
        self._slider.pack(side="left", fill="x", expand=True, padx=4)
        ttk.Button(nav, text="▶", width=3, command=lambda: self._step(1)).pack(side="left")
        self._frame_label = ttk.Label(nav, text="— / —", width=10)
        self._frame_label.pack(side="left", padx=6)

    # ── 데이터 로딩 ────────────────────────────────────────────────────────────

    def _load_rar(self) -> None:
        rar_path = self._path / "annotation.rar"
        if not rar_path.exists():
            self.after(0, lambda: self._status.set(f"annotation.rar 없음: {rar_path}"))
            return
        rar = rarfile.RarFile(str(rar_path))
        vids = sorted({
            n.split("/")[1]
            for n in rar.namelist()
            if n.startswith("annotation/") and len(n.split("/")) >= 3
            and n.split("/")[1].isdigit()
        })
        self._rar = rar
        self._all_videos = vids
        self.after(0, lambda: (
            self._status.set(f"영상 {len(vids)}개 로드됨"),
            self._refresh_list(),
        ))

    # ── 리스트 관리 ────────────────────────────────────────────────────────────

    def _refresh_list(self) -> None:
        split = self._split_var.get()
        lo, hi = (1, 1000) if split == "All" else _SPLITS[split]
        filtered = [v for v in self._all_videos if lo <= int(v) <= hi]
        self._listbox.delete(0, "end")
        for v in filtered:
            self._listbox.insert("end", f"{v}  [{_split_of(int(v))}]")

    def _on_video_select(self, _: tk.Event) -> None:
        sel = self._listbox.curselection()
        if not sel or not self._rar:
            return
        vid = self._listbox.get(sel[0]).split()[0]
        self._load_video(vid)

    # ── 영상 / 프레임 표시 ─────────────────────────────────────────────────────

    def _load_video(self, vid: str) -> None:
        self._vid_label.config(text=f"영상 {vid}  [{_split_of(int(vid))}]")
        self._frames = sorted([
            n for n in self._rar.namelist()
            if n.startswith(f"annotation/{vid}/maps/") and n.endswith(".png")
        ])
        total = len(self._frames)
        self._slider.config(from_=0, to=max(total - 1, 0))
        self._frame_idx = 0
        self._frame_var.set(0)
        self._frame_label.config(text=f"1 / {total}")
        if self._frames:
            self._render_frame(vid, 0)

    def _render_frame(self, vid: str, idx: int) -> None:
        sal_path = self._frames[idx]
        frame_num = Path(sal_path).stem
        fix_path = f"annotation/{vid}/fixation/{frame_num}.png"
        self._img_refs.clear()
        for name, canvas in ((sal_path, self._canvas_sal), (fix_path, self._canvas_fix)):
            try:
                img = Image.open(io.BytesIO(self._rar.read(name))).convert("RGB")
                img.thumbnail(_THUMB)
                photo = ImageTk.PhotoImage(img)
                canvas.config(width=img.width, height=img.height)
                canvas.create_image(0, 0, anchor="nw", image=photo)
                self._img_refs.append(photo)
            except Exception:
                canvas.delete("all")
                canvas.create_text(_THUMB[0] // 2, _THUMB[1] // 2,
                                   text="없음", fill="#666")
        self._frame_label.config(text=f"{idx + 1} / {len(self._frames)}")

    def _on_slider(self, val: str) -> None:
        idx = int(float(val))
        if idx == self._frame_idx or not self._frames:
            return
        self._frame_idx = idx
        sel = self._listbox.curselection()
        if sel:
            self._render_frame(self._listbox.get(sel[0]).split()[0], idx)

    def _step(self, delta: int) -> None:
        if not self._frames:
            return
        idx = max(0, min(len(self._frames) - 1, self._frame_idx + delta))
        self._frame_var.set(idx)
        self._frame_idx = idx
        sel = self._listbox.curselection()
        if sel:
            self._render_frame(self._listbox.get(sel[0]).split()[0], idx)
