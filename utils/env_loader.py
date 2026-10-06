from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent


def load_env(path: str | Path) -> dict[str, str]:
    """KEY=VALUE 형식의 .env 파일을 파싱해 딕셔너리로 반환한다."""
    env: dict[str, str] = {}
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        key, _, value = line.partition("=")
        env[key.strip()] = value.strip().strip('"')
    return env


def get_data_root() -> Path:
    """env/data.env 의 DATA_ROOT 를 반환한다. 파일이 없으면 기본값을 쓴다."""
    env_path = _PROJECT_ROOT / "env" / "data.env"
    if env_path.exists():
        val = load_env(env_path).get("DATA_ROOT", "")
        if val:
            return Path(val)
    return _PROJECT_ROOT / "outputs"


def get_model_root() -> Path:
    """env/model.env 의 MODEL_ROOT 를 반환한다. 파일이 없으면 기본값을 쓴다."""
    env_path = _PROJECT_ROOT / "env" / "model.env"
    if env_path.exists():
        val = load_env(env_path).get("MODEL_ROOT", "")
        if val:
            return Path(val)
    return Path("D:/models")
