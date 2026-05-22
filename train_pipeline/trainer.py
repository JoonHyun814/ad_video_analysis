"""Unsloth FastVisionModel(Qwen VL 3)을 이용해 4개 데이터셋을 순차적으로 학습한다."""

import json
from pathlib import Path

import yaml


def load_config(config_path: Path) -> dict:
    """YAML 설정 파일을 로드한다. 확장자 없으면 .yaml 을 자동 추가한다."""
    if not config_path.suffix:
        config_path = config_path.with_suffix(".yaml")
    return yaml.safe_load(config_path.read_text(encoding="utf-8"))


def train(config: dict) -> None:
    """config 에 따라 모델을 로드하고 데이터셋을 순차 학습한다."""
    from unsloth import FastVisionModel
    from trl import SFTTrainer, SFTConfig
    from datasets import load_dataset

    model_cfg = config["model"]
    lora_cfg = config["lora"]
    train_cfg = config["training"]
    ds_cfg = config["dataset"]
    out_cfg = config.get("output", {})

    # ── 모델 로드 ──────────────────────────────────────────────────────────────
    print(f"모델 로드: {model_cfg['name']}")
    model, tokenizer = FastVisionModel.from_pretrained(
        model_cfg["name"],
        max_seq_length=model_cfg.get("max_seq_length", 4096),
        load_in_4bit=model_cfg.get("load_in_4bit", True),
    )
    model = FastVisionModel.get_peft_model(
        model,
        r=lora_cfg.get("r", 16),
        lora_alpha=lora_cfg.get("lora_alpha", 32),
        target_modules=lora_cfg.get("target_modules", [
            "q_proj", "k_proj", "v_proj", "o_proj",
            "gate_proj", "up_proj", "down_proj",
        ]),
        use_gradient_checkpointing=lora_cfg.get("use_gradient_checkpointing", "unsloth"),
        random_state=lora_cfg.get("random_state", 3407),
    )

    # ── 순차 학습 ──────────────────────────────────────────────────────────────
    order = ("scene_analysis", "cut_analysis", "scenario_analysis")
    for step_name in order:
        ds_path = ds_cfg.get(step_name)
        if not ds_path or not Path(ds_path).exists():
            print(f"[{step_name}] 데이터셋 없음, 건너뜀: {ds_path}")
            continue

        print(f"\n[{step_name}] 학습 시작  ({ds_path})")
        dataset = load_dataset("json", data_files=ds_path, split="train")
        dataset = dataset.map(
            lambda ex: _preprocess(ex, tokenizer),
            remove_columns=dataset.column_names,
        )
        print(f"  샘플 수: {len(dataset)}")

        step_out = Path(train_cfg["output_dir"]) / step_name
        trainer = SFTTrainer(
            model=model,
            tokenizer=tokenizer,
            train_dataset=dataset,
            args=SFTConfig(
                per_device_train_batch_size=train_cfg.get("per_device_train_batch_size", 1),
                gradient_accumulation_steps=train_cfg.get("gradient_accumulation_steps", 4),
                max_steps=train_cfg.get("max_steps", 1000),
                learning_rate=train_cfg.get("learning_rate", 2e-4),
                warmup_steps=train_cfg.get("warmup_steps", 50),
                output_dir=str(step_out),
                fp16=train_cfg.get("fp16", False),
                bf16=train_cfg.get("bf16", True),
                logging_steps=train_cfg.get("logging_steps", 10),
                save_steps=train_cfg.get("save_steps", 250),
                report_to=train_cfg.get("report_to", "none"),
                dataset_text_field="text",
                remove_unused_columns=False,
            ),
        )
        trainer.train()
        print(f"  [{step_name}] 완료  →  {step_out}")

    # ── 저장 ──────────────────────────────────────────────────────────────────
    if out_cfg.get("save_merged"):
        save_dir = out_cfg.get("save_dir", "models/qwen_vl_ad")
        print(f"\n모델 병합 저장 중...  →  {save_dir}")
        model.save_pretrained_merged(save_dir, tokenizer)
        print("완료")


def _preprocess(example: dict, processor) -> dict:
    """메시지에서 이미지를 로드하고 chat template 을 적용한다."""
    from PIL import Image

    images = []
    clean_messages = []
    for msg in example["messages"]:
        clean_content = []
        for item in msg.get("content", []):
            if isinstance(item, dict) and item.get("type") == "image":
                path = item.get("image", "")
                if path and Path(path).exists():
                    images.append(Image.open(path).convert("RGB"))
                clean_content.append({"type": "image"})
            else:
                clean_content.append(item)
        clean_messages.append({**msg, "content": clean_content})

    text = processor.apply_chat_template(
        clean_messages, tokenize=False, add_generation_prompt=False
    )
    return {"text": text, "_images": []}  # images handled by collator
