# utils/

프로젝트 전반에서 재사용하는 공통 헬퍼. 새 LLM 호출·JSON 파싱·env 로딩을 구현하기 전에 반드시 여기서 기존 헬퍼를 확인한다.

로컬 Qwen2.5-VL 모델이 필요하면 `qwen_vl_caller.py` 의 `QwenVLModel` 을 사용한다.

세부 함수 목록과 사용법은 `utils/README.md` 를 읽어라.
