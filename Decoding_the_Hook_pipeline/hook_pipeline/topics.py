"""논문 3.3 후반 + 각주 6 — rationale 들을 BERTopic 으로 토픽화하고, 후보 토픽 수 중 perplexity 최소를 고른다.

perplexity 는 LDA 와 같은 정의를 BERTopic 에 적용한다:
  p(w|d) = Σ_k θ_dk · φ_kw,  θ = approximate_distribution(문서-토픽),  φ = 행 정규화한 c-TF-IDF(토픽-단어)
  perplexity = exp(-Σ_d Σ_w n_dw · log p(w|d) / Σ n_dw)
"""
from dataclasses import dataclass

import numpy as np
from bertopic import BERTopic
from hdbscan import HDBSCAN
from sentence_transformers import SentenceTransformer
from sklearn.feature_extraction.text import CountVectorizer
from umap import UMAP

MIN_DOCS = 10


@dataclass
class TopicFit:
    model: BERTopic
    topics: list[int]  # 문서별 할당 토픽 (-1 = 노이즈)
    distribution: np.ndarray  # 문서 × 토픽 (노이즈 제외) 분포
    perplexity: float
    candidate: int


def fit_best_topic_model(
    docs: list[str], candidates: list[int], min_cluster_size: int, embedding_model: str, seed: int,
) -> tuple[TopicFit, list[dict]]:
    """후보 nr_topics 마다 BERTopic 을 학습해 perplexity 가 가장 낮은 모델과 전체 점수표를 반환한다."""
    if len(docs) < MIN_DOCS:
        raise ValueError(f"토픽 모델링에는 최소 {MIN_DOCS}개 문서가 필요합니다 (현재 {len(docs)}개).")
    embedder = SentenceTransformer(embedding_model)
    embeddings = embedder.encode(docs, show_progress_bar=False)

    best: TopicFit | None = None
    scores: list[dict] = []
    for k in candidates:
        fit = _fit_one(docs, embeddings, embedder, k, min_cluster_size, seed)
        n_topics = int(fit.distribution.shape[1])
        scores.append({"nr_topics_candidate": k, "n_topics": n_topics, "perplexity": fit.perplexity})
        print(f"      nr_topics={k:>3} → 실제 토픽 {n_topics:>3}개, perplexity={fit.perplexity:.2f}")
        if best is None or fit.perplexity < best.perplexity:
            best = fit
    return best, scores


def _fit_one(docs, embeddings, embedder, k: int, min_cluster_size: int, seed: int) -> TopicFit:
    model = BERTopic(
        embedding_model=embedder,
        umap_model=UMAP(n_neighbors=min(15, len(docs) - 1), n_components=5, min_dist=0.0,
                        metric="cosine", random_state=seed),
        hdbscan_model=HDBSCAN(min_cluster_size=min_cluster_size, metric="euclidean",
                              cluster_selection_method="eom", prediction_data=True),
        vectorizer_model=CountVectorizer(stop_words="english"),
        top_n_words=10,
        nr_topics=k,
    )
    topics, _ = model.fit_transform(docs, embeddings)
    distribution, _ = model.approximate_distribution(docs)
    return TopicFit(model, list(topics), distribution, topic_perplexity(model, docs, distribution), k)


def topic_perplexity(model: BERTopic, docs: list[str], distribution: np.ndarray) -> float:
    """문서-토픽 분포와 c-TF-IDF 토픽-단어 분포로 코퍼스 perplexity 를 계산한다."""
    phi = model.c_tf_idf_[model._outliers:].toarray()  # 노이즈(-1) 행 제외, distribution 열 순서와 동일
    phi = _row_normalize(phi)
    theta = _row_normalize(np.asarray(distribution, dtype=float))
    counts = model.vectorizer_model.transform(docs).tocoo()
    if counts.nnz == 0 or phi.shape[0] == 0:
        return float("inf")
    p = np.einsum("ik,ik->i", theta[counts.row], phi[:, counts.col].T)
    log_likelihood = float(np.sum(counts.data * np.log(p + 1e-12)))
    return float(np.exp(-log_likelihood / counts.data.sum()))


def _row_normalize(mat: np.ndarray) -> np.ndarray:
    """행 합이 1 이 되게 하고, 합이 0 인 행은 균등분포로 둔다."""
    if mat.size == 0:
        return mat
    sums = mat.sum(axis=1, keepdims=True)
    uniform = np.full_like(mat, 1.0 / mat.shape[1])
    return np.where(sums > 0, mat / np.where(sums > 0, sums, 1.0), uniform)
