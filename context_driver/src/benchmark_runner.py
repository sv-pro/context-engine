#!/usr/bin/env python3
"""
Benchmark Runner CLI

Runs RAG benchmarks to evaluate retrieval quality and compare strategies.

Usage:
    python benchmark_runner.py --strategy super_hybrid --model gpt-4o-mini
    python benchmark_runner.py --all-strategies --model o1-mini
    python benchmark_runner.py --compare-models
"""

import argparse
import json
import sys
import os
from pathlib import Path
from typing import List, Dict

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from benchmark import BenchmarkQuery, BenchmarkEvaluator, EvaluationResult
from db import Database


def load_test_queries(test_file: str = "test_queries.json") -> List[BenchmarkQuery]:
    """Load test queries from JSON file."""
    test_path = Path(__file__).parent.parent / test_file
    
    with open(test_path, 'r') as f:
        data = json.load(f)
    
    queries = []
    for q in data['queries']:
        queries.append(BenchmarkQuery(
            id=q['id'],
            category=q['category'],
            query=q['query'],
            relevant_docs=q['relevant_docs'],
            relevant_chunks=q.get('relevant_chunks', []),
            expected_answer_contains=q['expected_answer_contains'],
            difficulty=q['difficulty'],
            reasoning_path=q.get('reasoning_path'),
            why_straightforward_fails=q.get('why_straightforward_fails'),
            why_sophisticated_succeeds=q.get('why_sophisticated_succeeds')
        ))
    
    return queries


def run_retrieval_benchmark(
    queries: List[BenchmarkQuery],
    strategy: str,
    db: Database
) -> List[EvaluationResult]:
    """
    Run retrieval benchmark for a given strategy.
    
    Args:
        queries: List of test queries
        strategy: Search strategy to use
        db: Database instance
    
    Returns:
        List of evaluation results
    """
    evaluator = BenchmarkEvaluator()
    results = []
    
    print(f"\n{'='*60}")
    print(f"Running benchmark with strategy: {strategy}")
    print(f"{'='*60}\n")
    
    for query in queries:
        print(f"Query {query.id} ({query.difficulty}): {query.query}")
        
        # Generate embedding for query
        from main import get_embedding
        query_vector = get_embedding(query.query)
        
        if not query_vector:
            print(f"  ❌ Failed to generate embedding")
            continue
        
        # Perform search
        if strategy in ["graph", "super_hybrid", "adaptive"]:
            from main import retrieve_context_docs
            # retrieve context docs returns (fpath, title, content, type, score)
            # db.search returns (fpath, title, content, score)
            # Adapter needed? No, retrieve_context_docs returns 5 items which matches db.search return signature.
            search_results = retrieve_context_docs(query.query, strategy=strategy, limit=5)
        else:
            search_results = db.search(query.query, query_vector, strategy=strategy, limit=5)
        
        # Create evidence pack
        evidence_pack = evaluator.create_evidence_pack(
            query=query.query,
            search_results=search_results,
            strategy=strategy,
            kb_state={"total_docs": len(search_results)}
        )
        
        # Evaluate
        eval_result = evaluator.evaluate_retrieval(query, evidence_pack)
        results.append(eval_result)
        
        # Print results
        if evidence_pack.gap_flag:
            print(f"  ⚠️  GAP: No evidence found!")
        else:
            print(f"  Evidence: {len(evidence_pack.fragments)} fragments")
            print(f"  Top sources: {[f.source_title for f in evidence_pack.fragments[:3]]}")
        
        print(f"  Relevant: {query.relevant_docs}")
        print(f"  P@3: {eval_result.precision_at_3:.2f} | R@3: {eval_result.recall_at_3:.2f} | MRR: {eval_result.mrr:.2f} | nDCG@5: {eval_result.ndcg_at_5:.2f}")
        print(f"  Debug: strategy={evidence_pack.debug['strategy']}, sim_range=[{evidence_pack.debug['min_similarity']:.3f}, {evidence_pack.debug['max_similarity']:.3f}]")
        
        if eval_result.precision_at_3 < 0.5:
            print(f"  ⚠️  Low precision!")
        if eval_result.mrr == 0:
            print(f"  ❌ No relevant results found")
        
        print()
    
    return results


def print_summary(strategy: str, results: List[EvaluationResult]):
    """Print summary statistics."""
    evaluator = BenchmarkEvaluator()
    aggregated = evaluator.aggregate_results(results)
    
    print(f"\n{'='*60}")
    print(f"Summary for {strategy}")
    print(f"{'='*60}")
    print(f"Mean Precision@3: {aggregated['mean_precision_at_3']:.3f}")
    print(f"Mean Precision@5: {aggregated['mean_precision_at_5']:.3f}")
    print(f"Mean Recall@3:    {aggregated['mean_recall_at_3']:.3f}")
    print(f"Mean Recall@5:    {aggregated['mean_recall_at_5']:.3f}")
    print(f"Mean MRR:         {aggregated['mean_mrr']:.3f}")
    print(f"Mean nDCG@5:      {aggregated['mean_ndcg_at_5']:.3f}")
    print(f"{'='*60}\n")


def compare_strategies(queries: List[BenchmarkQuery], strategies: List[str], db: Database):
    """Compare multiple strategies."""
    all_results = {}
    query_map = {q.id: q for q in queries}
    
    for strategy in strategies:
        results = run_retrieval_benchmark(queries, strategy, db)
        all_results[strategy] = results
        print_summary(strategy, results)
    
    # Print comparison table
    evaluator = BenchmarkEvaluator()
    
    # Prepare Stats
    stats = {}
    categories = set()
    
    for strategy, results in all_results.items():
        stats[strategy] = {}
        
        # Overall
        overall = evaluator.aggregate_results(results)
        if overall:
            overall['integral'] = (overall['mean_precision_at_3'] + overall['mean_recall_at_3'] + overall['mean_mrr'] + overall['mean_ndcg_at_5']) / 4
        stats[strategy]['OVERALL'] = overall
        
        # Per Category
        cat_buckets = {}
        for r in results:
            cat = query_map[r.query_id].category
            categories.add(cat)
            if cat not in cat_buckets:
                cat_buckets[cat] = []
            cat_buckets[cat].append(r)
            
        for cat, cat_results in cat_buckets.items():
            m = evaluator.aggregate_results(cat_results)
            if m:
                m['integral'] = (m['mean_precision_at_3'] + m['mean_recall_at_3'] + m['mean_mrr'] + m['mean_ndcg_at_5']) / 4
            stats[strategy][cat] = m

    cats_sorted = sorted(list(categories))
    
    # Markdown Table: Integral Scores by Category
    print("\n## Strategy Comparison - Integral Scores\n")
    print("*Integral = Average of P@3, R@3, MRR, nDCG@5*\n")
    
    # Header row
    headers = ["Strategy", "Overall"] + [c[:12] for c in cats_sorted]
    print("| " + " | ".join(headers) + " |")
    print("| " + " | ".join(["---"] * len(headers)) + " |")
    
    # Data rows
    for strategy in strategies:
        row = [strategy]
        overall_score = stats[strategy].get('OVERALL', {}).get('integral', 0.0)
        row.append(f"{overall_score:.3f}")
        
        for cat in cats_sorted:
            score = stats[strategy].get(cat, {}).get('integral', 0.0)
            row.append(f"{score:.3f}")
            
        print("| " + " | ".join(row) + " |")
    
    print()
    
    # Markdown Table: Standard Metrics
    comparison = evaluator.compare_strategies(all_results)
    
    print("\n## Standard Metrics (Overall)\n")
    print("| Strategy | P@3 | R@3 | MRR | nDCG@5 |")
    print("| --- | --- | --- | --- | --- |")
    
    for strategy, metrics in comparison.items():
        print(f"| {strategy} | "
              f"{metrics['mean_precision_at_3']:.3f} | "
              f"{metrics['mean_recall_at_3']:.3f} | "
              f"{metrics['mean_mrr']:.3f} | "
              f"{metrics['mean_ndcg_at_5']:.3f} |")
    
    print(f"{'='*60}\n")


def main():
    parser = argparse.ArgumentParser(description="Run RAG benchmarks")
    parser.add_argument(
        "--strategy",
        choices=["semantic", "keyword", "graph", "hybrid", "super_hybrid", "adaptive"],
        default="super_hybrid",
        help="Search strategy to benchmark"
    )
    parser.add_argument(
        "--all-strategies",
        action="store_true",
        help="Run benchmark on all strategies"
    )
    parser.add_argument(
        "--category",
        help="Filter queries by category (e.g., 'multi-hop', 'configuration')"
    )
    parser.add_argument(
        "--difficulty",
        choices=["easy", "medium", "hard"],
        help="Filter queries by difficulty"
    )
    
    args = parser.parse_args()
    
    # Load queries
    queries = load_test_queries()
    
    # Filter queries if requested
    if args.category:
        queries = [q for q in queries if q.category == args.category]
        print(f"Filtered to {len(queries)} queries in category '{args.category}'")
    
    if args.difficulty:
        queries = [q for q in queries if q.difficulty == args.difficulty]
        print(f"Filtered to {len(queries)} queries with difficulty '{args.difficulty}'")
    
    if not queries:
        print("No queries match the filters!")
        return
    
    # Initialize database
    db = Database()
    
    # Run benchmarks
    if args.all_strategies:
        strategies = ["semantic", "keyword", "graph", "hybrid", "super_hybrid", "adaptive"]
        compare_strategies(queries, strategies, db)
    else:
        results = run_retrieval_benchmark(queries, args.strategy, db)
        print_summary(args.strategy, results)


if __name__ == "__main__":
    main()
