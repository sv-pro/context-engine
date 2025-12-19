"""
RAG Benchmark System - Core Metrics and Evaluation

Implements retrieval quality metrics and end-to-end RAG evaluation.
"""

import math
from typing import List, Dict, Tuple, Set, Any
from dataclasses import dataclass


@dataclass
class RetrievalResult:
    """Single retrieval result."""
    doc_id: str
    title: str
    content: str
    section: str
    similarity: float
    rank: int


@dataclass
class BenchmarkQuery:
    """Test query with ground truth."""
    id: str
    category: str
    query: str
    relevant_docs: List[str]
    relevant_chunks: List[str]
    expected_answer_contains: List[str]
    difficulty: str
    reasoning_path: List[str] = None
    why_straightforward_fails: str = None
    why_sophisticated_succeeds: str = None


@dataclass
class EvaluationResult:
    """Results for a single query evaluation."""
    query_id: str
    precision_at_3: float
    precision_at_5: float
    recall_at_3: float
    recall_at_5: float
    mrr: float
    ndcg_at_5: float
    retrieved_docs: List[str]
    relevant_retrieved: List[str]


class RetrievalMetrics:
    """Implements standard retrieval quality metrics."""
    
    @staticmethod
    def precision_at_k(retrieved: List[str], relevant: Set[str], k: int) -> float:
        """
        Precision@K: How many of the top K results are relevant?
        
        Args:
            retrieved: List of retrieved document IDs (in rank order)
            relevant: Set of relevant document IDs
            k: Number of top results to consider
        
        Returns:
            Precision score (0.0 to 1.0)
        """
        if k == 0 or not retrieved:
            return 0.0
        
        top_k = retrieved[:k]
        relevant_in_top_k = sum(1 for doc in top_k if doc in relevant)
        return relevant_in_top_k / k
    
    @staticmethod
    def recall_at_k(retrieved: List[str], relevant: Set[str], k: int) -> float:
        """
        Recall@K: What fraction of all relevant docs are in top K?
        
        Args:
            retrieved: List of retrieved document IDs (in rank order)
            relevant: Set of relevant document IDs
            k: Number of top results to consider
        
        Returns:
            Recall score (0.0 to 1.0)
        """
        if not relevant or not retrieved:
            return 0.0
        
        top_k = retrieved[:k]
        relevant_in_top_k = sum(1 for doc in top_k if doc in relevant)
        return relevant_in_top_k / len(relevant)
    
    @staticmethod
    def mean_reciprocal_rank(retrieved: List[str], relevant: Set[str]) -> float:
        """
        MRR: How quickly do we find the first relevant result?
        
        Args:
            retrieved: List of retrieved document IDs (in rank order)
            relevant: Set of relevant document IDs
        
        Returns:
            MRR score (0.0 to 1.0)
        """
        for rank, doc in enumerate(retrieved, start=1):
            if doc in relevant:
                return 1.0 / rank
        return 0.0
    
    @staticmethod
    def ndcg_at_k(retrieved: List[str], relevant: Set[str], k: int) -> float:
        """
        Normalized Discounted Cumulative Gain@K
        
        Measures ranking quality with position weighting.
        Assumes binary relevance (relevant=1, not relevant=0).
        
        Args:
            retrieved: List of retrieved document IDs (in rank order)
            relevant: Set of relevant document IDs
            k: Number of top results to consider
        
        Returns:
            nDCG score (0.0 to 1.0)
        """
        if not retrieved or not relevant:
            return 0.0
        
        # Calculate DCG
        dcg = 0.0
        for i, doc in enumerate(retrieved[:k]):
            if doc in relevant:
                # Binary relevance: 1 if relevant, 0 otherwise
                relevance = 1.0
                # Discount by log2(rank + 1)
                dcg += relevance / math.log2(i + 2)
        
        # Calculate ideal DCG (all relevant docs at top)
        ideal_dcg = 0.0
        for i in range(min(k, len(relevant))):
            ideal_dcg += 1.0 / math.log2(i + 2)
        
        if ideal_dcg == 0:
            return 0.0
        
        return dcg / ideal_dcg
    
    @staticmethod
    def f1_score(precision: float, recall: float) -> float:
        """Calculate F1 score from precision and recall."""
        if precision + recall == 0:
            return 0.0
        return 2 * (precision * recall) / (precision + recall)


class BenchmarkEvaluator:
    """Evaluates retrieval and RAG quality."""
    
    def __init__(self):
        self.metrics = RetrievalMetrics()
    
    def evaluate_retrieval(
        self,
        query: BenchmarkQuery,
        retrieved_docs: List[str]
    ) -> EvaluationResult:
        """
        Evaluate retrieval quality for a single query.
        
        Args:
            query: Benchmark query with ground truth
            retrieved_docs: List of retrieved document IDs (in rank order)
        
        Returns:
            Evaluation results with all metrics
        """
        relevant = set(query.relevant_docs)
        
        # Calculate metrics
        p_at_3 = self.metrics.precision_at_k(retrieved_docs, relevant, 3)
        p_at_5 = self.metrics.precision_at_k(retrieved_docs, relevant, 5)
        r_at_3 = self.metrics.recall_at_k(retrieved_docs, relevant, 3)
        r_at_5 = self.metrics.recall_at_k(retrieved_docs, relevant, 5)
        mrr = self.metrics.mean_reciprocal_rank(retrieved_docs, relevant)
        ndcg = self.metrics.ndcg_at_k(retrieved_docs, relevant, 5)
        
        # Find which relevant docs were retrieved
        relevant_retrieved = [doc for doc in retrieved_docs if doc in relevant]
        
        return EvaluationResult(
            query_id=query.id,
            precision_at_3=p_at_3,
            precision_at_5=p_at_5,
            recall_at_3=r_at_3,
            recall_at_5=r_at_5,
            mrr=mrr,
            ndcg_at_5=ndcg,
            retrieved_docs=retrieved_docs[:5],  # Top 5
            relevant_retrieved=relevant_retrieved
        )
    
    def aggregate_results(self, results: List[EvaluationResult]) -> Dict[str, float]:
        """
        Aggregate evaluation results across multiple queries.
        
        Args:
            results: List of evaluation results
        
        Returns:
            Dict of aggregated metrics (means)
        """
        if not results:
            return {}
        
        return {
            "mean_precision_at_3": sum(r.precision_at_3 for r in results) / len(results),
            "mean_precision_at_5": sum(r.precision_at_5 for r in results) / len(results),
            "mean_recall_at_3": sum(r.recall_at_3 for r in results) / len(results),
            "mean_recall_at_5": sum(r.recall_at_5 for r in results) / len(results),
            "mean_mrr": sum(r.mrr for r in results) / len(results),
            "mean_ndcg_at_5": sum(r.ndcg_at_5 for r in results) / len(results),
        }
    
    def compare_strategies(
        self,
        strategy_results: Dict[str, List[EvaluationResult]]
    ) -> Dict[str, Dict[str, float]]:
        """
        Compare multiple search strategies.
        
        Args:
            strategy_results: Dict mapping strategy name to list of results
        
        Returns:
            Dict mapping strategy name to aggregated metrics
        """
        comparison = {}
        for strategy, results in strategy_results.items():
            comparison[strategy] = self.aggregate_results(results)
        return comparison
