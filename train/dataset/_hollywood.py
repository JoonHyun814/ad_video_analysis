"""Hollywood-2 액션 인식 데이터셋 시각화 패널 — AVI 클립 + 액션 레이블."""

import tkinter as tk
from pathlib import Path
from tkinter import ttk
from typing import Optional

import cv2
from PIL import Image, ImageTk

_ACTIONS = [
    "AnswerPhone", "DriveCar", "Eat", "FightPerson", "GetOutCar",
    "HandShake", "HugPerson", "Kiss", "Run", "SitDown", "SitUp", "StandUp",
]
_THUMB = (640, 360)


def _load_labels(clipsets_dir: Path) -> dict[str, dict[str, int]]:
    """clip_id → {action: +1/-1} 매핑을 반환한다."""
    result: dict[str, dict[str, int]] = {}
    for action in _ACTIONS:
        for split in ("train", "test"):
            f = clipsets_dir / f"{action}_{split}.txt"
            if not f.exists():
                continue
            for line in f.read_text(encoding="utf-8").splitlines():
                parts = line.strip().split()
                if len(parts) < 2:
                    continue
                clip_id, label = parts[0], int(parts[1])
                result.setdefault(clip_id, {})[action] = label
    return result


class HollywoodPanel(ttk.Frame):
    def __init__(self, parent: tk.Widget, dataset_path: Path) -> None:
        super().__init__(parent)
        self._path = dataset_path
        self._labels = _load_labels(dataset_path / "ClipSets")
        self._clips: list[str] = []
        self._cap: Optional[cv2.VideoCapture] = None
        self._total_frames = 0
        self._img_ref = None
        self._build_ui()
        self._refresh_list()

    # ── UI 구성 ────────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        paned = ttk.PanedWindow(self, orient="horizontal")
        paned.pack(fill="both", expand=True)

        left = ttk.Frame(paned, width=210)
        paned.add(left, weight=0)

        ttk.Label(left, text="Action 필터").pack(anchor="w", padx=4, pady=(6, 2))
        self._action_var = tk.StringVar(value="All")
        combo = ttk.Combobox(left, textvariable=self._action_var,
                             values=["All"] + _ACTIONS, state="readonly")
        combo.pack(fill="x", padx=4, pady=2)
        combo.bind("<<ComboboxSelected>>", lambda _: self._refresh_list())

        ttk.Label(left, text="Label 필터").pack(anchor="w", padx=4, pady=(6, 2))
        self._label_var = tk.StringVar(value="All")
        for text, val in (("All", "All"), ("+1  (positive)", "+1"), ("-1  (negative)", "-1")):
            ttk.Radiobutton(left, text=text, value=val, variable=self._label_var,
                            command=self._refresh_list).pack(anchor="w", padx=12)

        self._listbox = tk.Listbox(left, activestyle="dotbox", font=("Consolas", 8))
        sb = ttk.Scrollbar(left, command=self._listbox.yview)
        self._listbox.config(yscrollcommand=sb.set)
        self._listbox.pack(side="left", fill="both", expand=True, padx=(4, 0), pady=4)
        sb.pack(side="left", fill="y", pady=4)
        self._listbox.bind("<<ListboxSelect>>", self._on_clip_select)
        self._count_label = ttk.Label(left, text="")
        self._count_label.pack(padx=4, pady=2)

        right = ttk.Frame(paned)
        paned.add(right, weight=1)

        self._info_label = ttk.Label(right, text="← 클립을 선택하세요", font=("", 10, "bold"))
        self._info_label.pack(anchor="w", padx=8, pady=6)

        self._canvas = tk.Canvas(right, bg="#1a1a1a", width=_THUMB[0], height=_THUMB[1])
        self._canvas.pack(padx=8, pady=(0, 4))

        nav = ttk.Frame(right)
        nav.pack(fill="x", padx=8, pady=4)
        ttk.Button(nav, text="◀", width=3, command=lambda: self._step(-1)).pack(side="left")
        self._frame_var = tk.IntVar(value=0)
        self._slider = ttk.Scale(nav, orient="horizontal", variable=self._frame_var,
                                 command=self._on_slider)
        self._slider.pack(side="left", fill="x", expand=True, padx=4)
        ttk.Button(nav, text="▶", width=3, command=lambda: self._step(1)).pack(side="left")
        self._frame_label = ttk.Label(nav, text="— / —", width=10)
        self._frame_label.pack(side="left", padx=6)

        self._act_label = ttk.Label(right, text="", foreground="#555", wraplength=700)
        self._act_label.pack(anchor="w", padx=8)

    # ── 리스트 관리 ────────────────────────────────────────────────────────────

    def _refresh_list(self) -> None:
        action = self._action_var.get()
        lf = self._label_var.get()
        clips_dir = self._path / "AVIClips"
        all_clips = {p.stem for p in clips_dir.glob("*.avi")}

        if action == "All":
            pool = sorted(all_clips)
            if lf != "All":
                lv = int(lf)
                pool = [c for c in pool
                        if c in self._labels and lv in self._labels[c].values()]
        else:
            pool = sorted(
                c for c in self._labels
                if c in all_clips and action in self._labels[c]
                and (lf == "All" or self._labels[c][action] == int(lf))
            )

        self._clips = pool
        self._listbox.delete(0, "end")
        for c in pool:
            acts = self._labels.get(c, {})
            pos = sum(1 for v in acts.values() if v == 1)
            self._listbox.insert("end", f"{c}  (+{pos})")
        self._count_label.config(text=f"총 {len(pool)}개")

    def _on_clip_select(self, _: tk.Event) -> None:
        sel = self._listbox.curselection()
        if not sel:
            return
        clip_id = self._listbox.get(sel[0]).split()[0]
        avi = self._path / "AVIClips" / f"{clip_id}.avi"
        if self._cap:
            self._cap.release()
        self._cap = cv2.VideoCapture(str(avi))
        self._total_frames = int(self._cap.get(cv2.CAP_PROP_FRAME_COUNT))
        self._slider.config(from_=0, to=max(self._total_frames - 1, 0))
        self._frame_var.set(0)
        self._info_label.config(text=f"클립: {clip_id}")
        acts = self._labels.get(clip_id, {})
        self._act_label.config(
            text="  |  ".join(f"{a}: {'✓ +1' if v == 1 else '✗ −1'}"
                              for a, v in sorted(acts.items())) or "레이블 없음"
        )
        self._show_frame(0)

    # ── 프레임 표시 ────────────────────────────────────────────────────────────

    def _show_frame(self, idx: int) -> None:
        if not self._cap:
            return
        self._cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
        ret, frame = self._cap.read()
        if not ret:
            return
        img = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        img.thumbnail(_THUMB)
        photo = ImageTk.PhotoImage(img)
        self._canvas.config(width=img.width, height=img.height)
        self._canvas.create_image(0, 0, anchor="nw", image=photo)
        self._img_ref = photo
        self._frame_label.config(text=f"{idx + 1} / {self._total_frames}")

    def _on_slider(self, val: str) -> None:
        self._show_frame(int(float(val)))

    def _step(self, delta: int) -> None:
        idx = max(0, min(self._total_frames - 1, self._frame_var.get() + delta))
        self._frame_var.set(idx)
        self._show_frame(idx)
