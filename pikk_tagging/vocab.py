"""기법 어휘(vocab.json) 로딩과 표기 정규화. LLM 은 여기 정의된 id 만 출력할 수 있다."""
import json
import random
import re
from dataclasses import dataclass
from pathlib import Path

_VOCAB_PATH = Path(__file__).with_name("vocab.json")


@dataclass(frozen=True)
class Technique:
    id: str
    axis: str
    definition: str
    include: tuple[str, ...]
    exclude: tuple[str, ...]
    confusable: dict[str, str]
    aliases: tuple[str, ...]
    site_prior: float


@dataclass(frozen=True)
class Vocab:
    version: str
    axes: dict[str, dict]
    techniques: dict[str, Technique]

    def axis_techniques(self, axis: str) -> list[Technique]:
        """축에 속한 기법을 vocab.json 정의 순서대로 반환한다."""
        return [t for t in self.techniques.values() if t.axis == axis]

    def normalize_term(self, term: str) -> str | None:
        """자유 표기 문자열이 기존 기법의 id·별칭이면 표준 id 를, 아니면 None 을 반환한다."""
        key = _norm(term)
        if not key:
            return None
        for tech in self.techniques.values():
            if _norm(tech.id) in key or key in {_norm(a) for a in tech.aliases}:
                return tech.id
        return None


def _norm(text: str) -> str:
    return re.sub(r"[^0-9a-z가-힣]", "", text.lower())


def load_vocab(path: Path = _VOCAB_PATH) -> Vocab:
    """vocab.json 을 읽어 Vocab 으로 변환한다."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    techniques = {t["id"]: _to_technique(t) for t in raw["techniques"]}
    return Vocab(version=raw["version"], axes=raw["axes"], techniques=techniques)


def _to_technique(d: dict) -> Technique:
    return Technique(
        id=d["id"],
        axis=d["axis"],
        definition=d["definition"],
        include=tuple(d["include"]),
        exclude=tuple(d["exclude"]),
        confusable=dict(d["confusable"]),
        aliases=tuple(d["aliases"]),
        site_prior=float(d["site_prior"]),
    )


def shuffled(items: list, seed_key: str) -> list:
    """seed_key 에 대해 재현 가능한 순서로 섞은 복사본을 반환한다 (순서 편향 완화용)."""
    out = list(items)
    random.Random(seed_key).shuffle(out)
    return out
