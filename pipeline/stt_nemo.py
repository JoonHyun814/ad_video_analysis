"""NeMo MSDD 화자 분리: 설정 생성 및 diarize() 진입점."""

import json
import tempfile
from pathlib import Path

# NeMo MSDD 설정 — diar_infer_telephonic.yaml 기반 파라미터를 Python dict 로 내재화
_CFG = {
    "num_workers": 0, "sample_rate": 16000, "batch_size": 64,
    "device": None, "verbose": False,
    "diarizer": {
        "manifest_filepath": None, "out_dir": None,
        "oracle_vad": False, "collar": 0.25, "ignore_overlap": True,
        "vad": {
            "model_path": "vad_multilingual_marblenet",
            "external_vad_manifest": None,
            "parameters": {
                "window_length_in_sec": 0.15, "shift_length_in_sec": 0.01,
                "smoothing": "median", "overlap": 0.5,
                "onset": 0.8, "offset": 0.6,
                "pad_onset": 0.1, "pad_offset": -0.05,
                "min_duration_on": 0.1, "min_duration_off": 0.2,
                "filter_speech_first": True,
            },
        },
        "speaker_embeddings": {
            "model_path": "titanet_large",
            "parameters": {
                "window_length_in_sec": [1.5, 1.25, 1.0, 0.75, 0.5],
                "shift_length_in_sec": [0.75, 0.625, 0.5, 0.375, 0.25],
                "multiscale_weights": [1, 1, 1, 1, 1],
                "save_embeddings": True,
            },
        },
        "clustering": {
            "parameters": {
                "oracle_num_speakers": False, "max_num_speakers": 8,
                "enhanced_count_thres": 80, "max_rp_threshold": 0.25,
                "sparse_search_volume": 30, "maj_vote_spk_count": False,
                "chunk_cluster_count": 50, "embeddings_per_chunk": 10000,
            },
        },
        "msdd_model": {
            "model_path": "diar_msdd_telephonic",
            "parameters": {
                "use_speaker_model_from_ckpt": True, "infer_batch_size": 25,
                "sigmoid_threshold": [0.7], "seq_eval_mode": False,
                "split_infer": True, "diar_window_length": 50,
                "overlap_infer_spk_limit": 5,
            },
            "test_ds": {
                "manifest_filepath": None, "emb_dir": None,
                "batch_size": 1, "num_workers": 0,
            },
        },
    },
}


def diarize(audio_path: Path, device: str) -> list[tuple[int, int, int]]:
    """NeMo MSDD로 화자 분리를 수행하고 [(start_ms, end_ms, speaker_id), ...] 를 반환한다."""
    from nemo.collections.asr.models.msdd_models import NeuralDiarizer
    from nemo.collections.asr.parts.utils.speaker_utils import rttm_to_labels
    from omegaconf import OmegaConf

    with tempfile.TemporaryDirectory() as tmp_str:
        tmp = Path(tmp_str)
        wav = tmp / "mono_file.wav"
        wav.write_bytes(audio_path.read_bytes())

        manifest = tmp / "manifest.json"
        manifest.write_text(json.dumps({
            "audio_filepath": str(wav), "offset": 0, "duration": None,
            "label": "infer", "text": "-", "rttm_filepath": None, "uem_filepath": None,
        }))

        cfg = OmegaConf.create(_CFG)
        cfg.diarizer.manifest_filepath = str(manifest)
        cfg.diarizer.out_dir = str(tmp)
        cfg.diarizer.msdd_model.test_ds.manifest_filepath = str(manifest)

        model = NeuralDiarizer(cfg=cfg).to(device)
        model._initialize_configs(
            manifest_path=str(manifest), max_speakers=8, num_speakers=None,
            tmpdir=str(tmp), batch_size=24, num_workers=0, verbose=False,
        )
        model.clustering_embedding.clus_diar_model._diarizer_params.out_dir = str(tmp)
        model.clustering_embedding.clus_diar_model._diarizer_params.manifest_filepath = str(manifest)
        model.msdd_model.cfg.test_ds.manifest_filepath = str(manifest)
        model.diarize()

        labels = rttm_to_labels(str(tmp / "pred_rttms" / "mono_file.rttm"))

    result = []
    for lbl in labels:
        s, e, sp = lbl.split()
        result.append((int(float(s) * 1000), int(float(e) * 1000), int(sp.split("_")[1])))
    return sorted(result)
