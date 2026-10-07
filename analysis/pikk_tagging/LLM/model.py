"""Qwen2.5-VL 모델 — 공통 구현은 utils.qwen_vl_caller 에 있다."""
from utils.qwen_vl_caller import InferenceResult, QwenVLModel

__all__ = ["QwenVLModel", "InferenceResult"]
