# RAG 유형별 정리 — 특징·장단점·논문·이 저장소 구현

이 저장소가 실제로 구현한 5가지 RAG 방식(Hybrid → Contextual → Multimodal → Graph, 그리고
원래부터 있던 Agentic 패턴)을 이론적 배경과 함께 정리한다. 각 절은 baseline인 Vector RAG
대비 무엇을 보완하는지, 트레이드오프가 뭔지, 관련 논문, 이 저장소의 실제 구현 위치 순으로
구성했다. 구체적인 API/파라미터 스펙은 [`README.md`](README.md)와
[`../server/MCP_SPEC.md`](../server/MCP_SPEC.md)를 참고한다.

---

## 0. Vector(Naive) RAG — 비교 기준

**정의**: 쿼리와 문서를 같은 임베딩 공간에 매핑해 코사인 유사도로 top-k를 검색, 그대로 LLM
컨텍스트에 넣는 가장 기본적인 형태. 이 저장소의 모든 RAG 확장은 이 baseline을 보완한다.

- **장점**: 구현이 단순하고, 키워드가 정확히 일치하지 않아도 의미가 비슷하면 찾는다(동의어·
  표현 차이에 강함).
- **단점**: 브랜드명·숫자처럼 정확히 일치해야 하는 키워드에 약하다(임베딩 유사도가 뭉개버림).
  텍스트로 표현되지 않은 정보(시각적 특징 등)는 애초에 검색 대상이 아니다. 여러 문서에 걸친
  관계·패턴 질의를 못 한다. 청킹된 요약만 있으면 원본 디테일을 놓친다.
- **관련 논문**:
  - Lewis et al., *"Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks"*,
    NeurIPS 2020 — RAG라는 용어 자체를 정립한 원 논문.
  - Karpukhin et al., *"Dense Passage Retrieval for Open-Domain Question Answering"*,
    EMNLP 2020 — dense retrieval(DPR)의 기반.
- **이 저장소 구현**: `db/chromadb/search_query.py`(`search()`) — `BAAI/bge-m3` 임베딩,
  `search_chromadb` 도구.

---

## 1. Hybrid RAG

**정의**: Dense(의미) 검색과 Sparse(키워드) 검색을 함께 수행해 결과를 결합한다. 서로 다른
실패 모드를 보완하는 게 핵심 — dense는 "의미는 비슷한데 단어가 다른" 걸 잘 찾고, sparse는
"단어가 정확히 일치해야 하는" 걸 잘 찾는다.

- **장점**: 브랜드명·숫자·전문 용어처럼 정확 매칭이 중요한 쿼리에서 recall이 크게 개선된다.
  두 신호를 합치는 방식(RRF 등)이 스코어 정규화 없이도 안정적으로 동작한다.
- **단점**: 검색 비용이 커진다(두 인덱스 관리 + 결합 로직). Sparse 인덱스가 형태소 분석 없이
  단순 토크나이저면(이 저장소의 문자 bigram처럼) 교착어(한국어 등)에서 정밀도가 떨어질 수
  있다. 결합 가중치/전략에 따라 결과가 민감하게 바뀔 수 있다.
- **관련 논문**:
  - Cormack, Clarke, Büttcher, *"Reciprocal Rank Fusion outperforms Condorcet and
    individual Rank Learning Methods"*, SIGIR 2009 — 이 저장소가 쓰는 RRF 결합 기법의 출처.
  - Robertson & Zaragoza, *"The Probabilistic Relevance Framework: BM25 and Beyond"*,
    Foundations and Trends in Information Retrieval, 2009 — BM25 이론적 기반.
- **이 저장소 구현**: `db/chromadb/hybrid_search.py` — dense(`search_query.search` 재사용) +
  BM25(문자 bigram 토크나이저, 한국어 조사 변형에 부분 매칭) → RRF 결합. `search_chromadb_hybrid`
  도구.

---

## 2. Contextual / Long-context RAG

**정의**: 검색은 항상 청킹된 요약본을 대상으로 하지만, 필요할 때는 청킹을 우회해 원본
전체를 컨텍스트에 채우는 방식. "검색 대 긴 컨텍스트"를 이분법으로 보지 않고, 검색으로 좁힌
뒤 필요하면 원본을 통째로 준다.

- **장점**: 요약 단계에서 버려진 디테일(예: 이 저장소의 `scenario.py`가 압축하는 `cast`/
  `scenes` 원문)에 접근할 수 있다. 청크 하나만으론 답할 수 없는 질문(전체 흐름 파악 등)에
  강하다.
- **단점**: 원본 전체를 넣으면 토큰 비용이 커지고, 긴 컨텍스트일수록 모델이 중간 정보를 놓치는
  경향이 있다("lost in the middle"). 검색 없이 무조건 원본을 채우면 애초에 RAG를 쓰는 이유가
  옅어진다 — 검색으로 좁힌 뒤에만 써야 한다.
- **관련 논문**:
  - Liu et al., *"Lost in the Middle: How Language Models Use Long Contexts"*, TACL 2024 —
    긴 컨텍스트 중간부에 있는 정보를 모델이 잘 활용하지 못한다는 것을 실증. 이 저장소의
    `scenario.py`가 `cast`/`scenes` 원문 대신 개수만 임베딩에 넣는 설계 근거이기도 하다.
  - Anthropic, *"Introducing Contextual Retrieval"*, Anthropic Engineering Blog, 2024 —
    학술 논문은 아니지만, 청크 임베딩 전에 문서 전체 맥락을 요약해 붙이는 기법으로 이 카테고리의
    실무 표준 레퍼런스.
- **이 저장소 구현**: `db/chromadb/show_by_video_id.py::fetch_by_video_id()` — 검색 도구로
  이미 찾은 `video_id`의 원본 레코드 전체(청킹 우회)를 반환. `fetch_by_video_id` 도구.

---

## 3. Multimodal RAG

**정의**: 텍스트뿐 아니라 이미지(또는 다른 모달리티)를 같은/호환되는 임베딩 공간에 넣어
교차 모달 검색(자연어 → 이미지, 또는 이미지 → 이미지)을 가능하게 한다.

- **장점**: "보라색 단색 배경", "6분할 모자이크"처럼 분석가가 텍스트로 남기지 않은 순수
  시각적 특징도 검색 가능해진다 — 텍스트 요약의 한계를 근본적으로 벗어난다.
- **단점**: 별도 비전 인코더가 필요하고(추가 모델 로딩/추론 비용), 텍스트 인코더가 다국어를
  제대로 지원하지 않으면(영문 중심 CLIP처럼) 비영어권 쿼리 품질이 떨어진다. 검색 결과가
  이미지 자체가 아니라 메타데이터/경로라, 실제로 "보려면" 호출측이 별도로 파일에 접근해야
  한다.
- **관련 논문**:
  - Radford et al., *"Learning Transferable Visual Models From Natural Language
    Supervision"* (CLIP), ICML 2021 — 이미지·텍스트를 같은 임베딩 공간에 매핑하는 대조 학습
    기법의 원 논문. 이 저장소가 CLIP 계열(`clip-ViT-B-32`/`clip-ViT-B-32-multilingual-v1`)을
    쓰는 근거.
  - Yasunaga et al., *"Retrieval-Augmented Multimodal Language Modeling"* (RA-CM3),
    ICML 2023 — 텍스트+이미지 혼합 검색-생성 구조.
  - Chen et al., *"MuRAG: Multimodal Retrieval-Augmented Generator"*, EMNLP 2022 — 이미지·
    텍스트 코퍼스를 함께 검색해 답을 생성하는 멀티모달 RAG 구조.
- **이 저장소 구현**: `db/chromadb/importers/keyframe_visual.py`(적재) +
  `db/chromadb/visual_search.py`(검색) — 이미지는 `clip-ViT-B-32`로, 검색 쿼리(한국어 포함)는
  `clip-ViT-B-32-multilingual-v1`로 인코딩해 같은 공간에서 비교. `search_visual` 도구.

---

## 4. Graph RAG

**정의**: 문서를 독립된 청크가 아니라 노드-엣지 그래프(엔티티·관계)로 구조화해, 여러 문서에
걸친 다단(multi-hop) 관계 질의를 가능하게 한다.

- **장점**: 벡터 검색은 "쿼리 하나 → 유사 문서"만 가능하지만, 그래프는 "이 조건을 만족하는
  여러 캠페인에서 공통으로 나타나는 패턴"처럼 집계·순회 질의에 강하다. 서사 구조·인과관계처럼
  관계 자체가 중요한 정보를 명시적으로 모델링한다.
- **단점**: 그래프 구축 자체가 비용이 크다(엔티티/관계 추출 정규화 필요). 이 저장소처럼 원본
  데이터에 형식적 연결이 없으면(역할 순서 ↔ 컷 번호) best-effort 가정에 의존해야 하고, 정확도가
  원본 데이터 품질에 크게 좌우된다. Cypher 같은 그래프 쿼리 언어는 팀 러닝 커브가 있고, LLM에게
  원시 쿼리 실행 권한을 주면 안전성 문제가 생긴다(이 저장소는 그래서 안전한 함수 1개만 도구로
  노출).
- **관련 논문**:
  - Edge et al. (Microsoft Research), *"From Local to Global: A Graph RAG Approach to
    Query-Focused Summarization"*, 2024 — "GraphRAG"라는 이름을 대중화한 논문. 커뮤니티 탐지로
    문서 전체를 계층적으로 요약해 전역 질의에 답하는 구조(이 저장소는 그 정도로 정교하진 않고,
    명시적 스키마 기반 그래프에 가깝다).
  - Mishra, Niroula, Yadav, Thakur, Gyawali, Gaire, *"SoK: Agentic Retrieval-Augmented
    Generation (RAG): Taxonomy, Architectures, Evaluation, and Research Directions"*,
    arXiv:2603.07379, 2026 — Graph RAG를 포함한 Agentic RAG 전반의 분류체계(4절 참고).
- **이 저장소 구현**: `db/graph/`(Kùzu, 임베디드 그래프 DB) — Campaign/Sequence/Element/Persona
  노드, `HAS_SEQUENCE`/`INCLUDES_ELEMENT`/`TRANSITIONS_TO`/`HAS_TARGET_PERSONA` 엣지.
  원시 Cypher는 노출하지 않고 `role_element_frequency()` 하나만 `search_graph_pattern`
  도구로 노출. 스키마·설계 근거는 [`README.md`](README.md)의 "Graph" 절 참고.

---

## 5. Agentic RAG

**정의**: 검색을 전처리 단계가 아니라, LLM이 스스로 "지금 검색이 필요한가/어떤 도구를 쓸까/
결과가 충분한가"를 판단하며 자율적으로 호출하는 도구(tool)로 다루는 방식. 이 저장소의
`search_chromadb`/`search_chromadb_hybrid`/`fetch_by_video_id`/`search_visual`/
`search_graph_pattern` 다섯 도구가 전부 이 패턴 위에서 동작한다 — LLM이 자율적으로 어느
도구를 언제 호출할지 고른다(SoK 논문 분류상 "on-demand retrieval" + "tool-mediated
interaction").

- **장점**: 검색이 필요 없는 쿼리에 불필요한 검색을 안 한다(고정 top-k 강제 주입 대비).
  여러 검색 백엔드(dense/hybrid/visual/graph) 중 쿼리 성격에 맞는 걸 LLM이 스스로 고른다 —
  이 저장소 도구 설명(`description`)에 "이럴 때 이 도구를, 저럴 때 저 도구를" 명시해 라우팅을
  유도한다. 결과가 부족하면 다른 도구로 재시도하는 등 유연한 다단 전략이 가능하다.
- **단점**: LLM의 도구 선택 판단이 틀릴 수 있다(잘못된 도구, 과도한 반복 호출). 호출 비용/
  지연이 단일 검색보다 커진다(추론+도구 호출 왕복). 검색 결과의 관련성·근거성을 LLM이
  스스로 비평(critique)하지 않으면(Self-RAG 식 반성 토큰 없이) 관련 없는 결과를 그대로 믿고
  넘어갈 위험이 있다 — 이 저장소는 아직 이 비평 단계가 없다(향후 확장 후보).
- **관련 논문**:
  - Asai, Wu, Wang, Sil, Hajishirzi, *"Self-RAG: Learning to Retrieve, Generate, and
    Critique through Self-Reflection"*, arXiv:2310.11511 (ICLR 2024) — 검색 필요 여부·검색
    결과 관련성·생성의 근거성을 모델이 스스로 판단하는 reflection 토큰 기법. 이 저장소는 학습된
    reflection 토큰 대신 도구 설명 텍스트로 같은 역할(언제 검색할지, 어느 도구를 쓸지)을
    프롬프트 레벨에서 유도한다.
  - Yao, Zhao, Yu, Du, Shafran, Narasimhan, Cao, *"ReAct: Synergizing Reasoning and Acting
    in Language Models"*, ICLR 2023 — 추론과 도구 호출(action)을 번갈아 수행하는 에이전트
    패턴의 기반. `claude -p`/Claude API의 tool_use 루프가 이 패턴 위에 있다.
  - Mishra, Niroula, Yadav, Thakur, Gyawali, Gaire, *"SoK: Agentic Retrieval-Augmented
    Generation (RAG): Taxonomy, Architectures, Evaluation, and Research Directions"*,
    arXiv:2603.07379, 2026 — Agentic RAG를 POMDP로 정식화하고, Hybrid/Graph/Multimodal 등을
    포함한 전체 분류체계·아키텍처 패턴·실패 모드(retrieval drift, 환각 증폭 등)를 정리한
    시스템화 논문. 이 저장소의 5개 RAG 확장 설계를 계획할 때 참고했다.
- **이 저장소 구현**: `db/chromadb/mcp_server.py`(stdio, 로컬 `claude -p`) /
  `server/mcp_server.py`(네트워크, Streamable HTTP) — 5개 도구를 FastMCP로 노출, 도구
  `description`에 "언제 이 도구를 쓰고 언제 다른 도구를 써야 하는지"를 명시해 LLM의 자율
  선택을 유도. `db/chromadb/tool_definitions.py`가 MCP·Anthropic API tool_use 양쪽이 공유하는
  단일 스키마 소스.

---

## 요약 표

| 유형 | 보완하는 것 | 핵심 트레이드오프 | 이 저장소 도구 |
|---|---|---|---|
| Vector(baseline) | – | 정확 매칭에 약함 | `search_chromadb` |
| Hybrid | 정확 매칭(브랜드명·숫자) | 인덱스 2배, 토크나이저 품질 의존 | `search_chromadb_hybrid` |
| Contextual/Long-context | 청킹으로 손실된 디테일 | 토큰 비용, lost-in-the-middle | `fetch_by_video_id` |
| Multimodal | 텍스트로 안 남는 시각 정보 | 별도 인코더, 다국어 텍스트 타워 필요 | `search_visual` |
| Graph | 문서 간 관계·패턴 | 구축 비용, 원본 데이터 연결 품질 의존 | `search_graph_pattern` |
| Agentic | 언제·어떤 검색을 할지 LLM이 판단 | 잘못된 도구 선택 위험, 자기비평 부재 | 도구 5개 전체 |
