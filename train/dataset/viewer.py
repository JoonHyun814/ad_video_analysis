"""DHF1K / Hollywood-2 데이터셋 시각화 GUI.

실행:
    python -m train.dataset.viewer
    python -m train.dataset.viewer --dhf1k D:/dataset/DHF1K --hollywood2 D:/dataset/Hollywood-2/Hollywood2
"""

import argparse
import tkinter as tk
from pathlib import Path
from tkinter import ttk

from train.dataset._dhf1k import DHF1KPanel
from train.dataset._hollywood import HollywoodPanel
from utils.env_loader import get_dhf1k_path, get_hollywood2_path


def _parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Dataset Viewer — DHF1K / Hollywood-2")
    ap.add_argument("--dhf1k", type=Path, default=None,
                    help="DHF1K 데이터셋 루트 (기본: env/data.env DHF1K_PATH)")
    ap.add_argument("--hollywood2", type=Path, default=None,
                    help="Hollywood-2 루트 (기본: env/data.env HOLLYWOOD2_PATH)")
    return ap.parse_args()


def main() -> None:
    args = _parse_args()
    dhf1k_path = args.dhf1k or get_dhf1k_path()
    hw2_path = args.hollywood2 or get_hollywood2_path()

    root = tk.Tk()
    root.title("Dataset Viewer — DHF1K / Hollywood-2")
    root.geometry("1280x760")

    nb = ttk.Notebook(root)
    nb.pack(fill="both", expand=True, padx=4, pady=4)

    dhf_tab = ttk.Frame(nb)
    hw_tab = ttk.Frame(nb)
    nb.add(dhf_tab, text="  DHF1K  ")
    nb.add(hw_tab, text="  Hollywood-2  ")

    DHF1KPanel(dhf_tab, dhf1k_path).pack(fill="both", expand=True)
    HollywoodPanel(hw_tab, hw2_path).pack(fill="both", expand=True)

    root.mainloop()


if __name__ == "__main__":
    main()
