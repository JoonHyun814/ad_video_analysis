from pathlib import Path


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
