"""
LLM Cost Tracking module.
Logs all LLM API requests and provides cost estimation with aggregations.
"""

import os
import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import List, Dict, Optional, Any
import psycopg2
from psycopg2.extras import RealDictCursor, Json

logger = logging.getLogger(__name__)

# Cost per 1K tokens (USD)
COST_PER_1K_TOKENS = {
    # OpenAI
    "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},
    "gpt-4o": {"input": 0.005, "output": 0.015},
    "gpt-4-turbo": {"input": 0.01, "output": 0.03},
    "gpt-3.5-turbo": {"input": 0.0005, "output": 0.0015},
    
    # Anthropic
    "claude-3-haiku-20240307": {"input": 0.00025, "output": 0.00125},
    "claude-3-sonnet-20240229": {"input": 0.003, "output": 0.015},
    "claude-3-opus-20240229": {"input": 0.015, "output": 0.075},
    
    # Embeddings (Local/Ollama - Free)
    "mxbai-embed-large": {"input": 0.0, "output": 0},
    "mxbai-embed-large:latest": {"input": 0.0, "output": 0},
    "nomic-embed-text": {"input": 0.0, "output": 0},
    "nomic-embed-text:latest": {"input": 0.0, "output": 0},
    
    # Embeddings (Paid)
    "text-embedding-3-small": {"input": 0.00002, "output": 0},
    "text-embedding-3-large": {"input": 0.00013, "output": 0},
    
    # Local (free)
    "llama3": {"input": 0, "output": 0},
    "llama3.2": {"input": 0, "output": 0},
    "llama3.2:latest": {"input": 0, "output": 0},
    "ollama/llama3": {"input": 0, "output": 0},
}


def estimate_tokens(text: str) -> int:
    """Rough token estimation (~4 chars per token)."""
    if not text:
        return 0
    return len(text) // 4


def calculate_cost(model: str, input_tokens: int, output_tokens: int = 0) -> float:
    """
    Calculate estimated cost in USD.
    
    Args:
        model: Model name
        input_tokens: Number of input tokens
        output_tokens: Number of output tokens
    
    Returns:
        Estimated cost in USD
    """
    # Normalize model name
    model_lower = model.lower()
    
    # Find matching cost entry
    costs = None
    for key, value in COST_PER_1K_TOKENS.items():
        if key.lower() in model_lower or model_lower in key.lower():
            costs = value
            break
    
    if costs is None:
        # Default to free (local model)
        return 0.0
    
    input_cost = (input_tokens / 1000) * costs["input"]
    output_cost = (output_tokens / 1000) * costs.get("output", 0)
    
    return input_cost + output_cost


class CostTracker:
    """Tracks LLM API costs with database persistence."""
    
    def __init__(self, db_connection):
        """
        Initialize the CostTracker.
        
        Args:
            db_connection: psycopg2 connection object
        """
        self.conn = db_connection
        self._ensure_table()
    
    def _ensure_table(self):
        """Create cost_log table if it doesn't exist."""
        with self.conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS brain.cost_log (
                    id SERIAL PRIMARY KEY,
                    timestamp TIMESTAMP DEFAULT NOW(),
                    operation TEXT NOT NULL,
                    model TEXT NOT NULL,
                    input_tokens INT DEFAULT 0,
                    output_tokens INT DEFAULT 0,
                    estimated_cost DECIMAL(10, 6) DEFAULT 0,
                    latency_ms INT DEFAULT 0,
                    metadata JSONB DEFAULT '{}'::jsonb
                );
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_cost_log_timestamp 
                ON brain.cost_log(timestamp);
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_cost_log_model 
                ON brain.cost_log(model);
            """)
            logger.info("Cost tracking table initialized")
    
    def log_request(
        self,
        operation: str,
        model: str,
        input_tokens: int,
        output_tokens: int = 0,
        latency_ms: int = 0,
        metadata: Optional[Dict] = None
    ) -> int:
        """
        Log an LLM API request.
        
        Args:
            operation: Type of operation ('embedding', 'chat', 'meta-prompt')
            model: Model name
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            latency_ms: Response latency in milliseconds
            metadata: Additional metadata
        
        Returns:
            Log entry ID
        """
        cost = calculate_cost(model, input_tokens, output_tokens)
        
        with self.conn.cursor() as cur:
            cur.execute("""
                INSERT INTO brain.cost_log 
                (operation, model, input_tokens, output_tokens, estimated_cost, latency_ms, metadata)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING id;
            """, (
                operation,
                model,
                input_tokens,
                output_tokens,
                cost,
                latency_ms,
                Json(metadata or {})
            ))
            log_id = cur.fetchone()[0]
            
        logger.debug(f"Logged {operation} request: {model}, {input_tokens}+{output_tokens} tokens, ${cost:.6f}")
        return log_id
    
    def get_summary(self, days: int = 7) -> Dict[str, Any]:
        """
        Get cost summary for the last N days.
        
        Returns:
            Summary with total cost, requests, and breakdowns
        """
        cutoff = datetime.now() - timedelta(days=days)
        
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Total cost and requests
            cur.execute("""
                SELECT 
                    COALESCE(SUM(estimated_cost), 0) as total_cost,
                    COUNT(*) as total_requests,
                    COALESCE(SUM(input_tokens), 0) as total_input_tokens,
                    COALESCE(SUM(output_tokens), 0) as total_output_tokens
                FROM brain.cost_log
                WHERE timestamp > %s;
            """, (cutoff,))
            totals = cur.fetchone()
            
            # By model
            cur.execute("""
                SELECT model, 
                       COALESCE(SUM(estimated_cost), 0) as cost,
                       COUNT(*) as requests
                FROM brain.cost_log
                WHERE timestamp > %s
                GROUP BY model
                ORDER BY cost DESC;
            """, (cutoff,))
            by_model = {row['model']: float(row['cost']) for row in cur.fetchall()}
            
            # By operation
            cur.execute("""
                SELECT operation, 
                       COALESCE(SUM(estimated_cost), 0) as cost,
                       COUNT(*) as requests
                FROM brain.cost_log
                WHERE timestamp > %s
                GROUP BY operation
                ORDER BY cost DESC;
            """, (cutoff,))
            by_operation = {row['operation']: float(row['cost']) for row in cur.fetchall()}
            
            return {
                "period_days": days,
                "total_cost_usd": float(totals['total_cost']),
                "total_requests": totals['total_requests'],
                "total_input_tokens": totals['total_input_tokens'],
                "total_output_tokens": totals['total_output_tokens'],
                "by_model": by_model,
                "by_operation": by_operation
            }
    
    def get_daily_breakdown(self, days: int = 7) -> List[Dict]:
        """
        Get daily cost breakdown.
        
        Returns:
            List of daily cost entries
        """
        cutoff = datetime.now() - timedelta(days=days)
        
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT 
                    DATE(timestamp) as date,
                    COALESCE(SUM(estimated_cost), 0) as cost,
                    COUNT(*) as requests,
                    COALESCE(SUM(input_tokens), 0) as input_tokens,
                    COALESCE(SUM(output_tokens), 0) as output_tokens
                FROM brain.cost_log
                WHERE timestamp > %s
                GROUP BY DATE(timestamp)
                ORDER BY date DESC;
            """, (cutoff,))
            
            return [
                {
                    "date": str(row['date']),
                    "cost": float(row['cost']),
                    "requests": row['requests'],
                    "input_tokens": row['input_tokens'],
                    "output_tokens": row['output_tokens']
                }
                for row in cur.fetchall()
            ]
    
    def get_recent_requests(self, limit: int = 50) -> List[Dict]:
        """
        Get recent request logs.
        
        Returns:
            List of recent request entries
        """
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT 
                    id,
                    timestamp,
                    operation,
                    model,
                    input_tokens,
                    output_tokens,
                    estimated_cost,
                    latency_ms,
                    metadata
                FROM brain.cost_log
                ORDER BY timestamp DESC
                LIMIT %s;
            """, (limit,))
            
            return [
                {
                    "id": row['id'],
                    "timestamp": row['timestamp'].isoformat() if row['timestamp'] else None,
                    "operation": row['operation'],
                    "model": row['model'],
                    "input_tokens": row['input_tokens'],
                    "output_tokens": row['output_tokens'],
                    "cost": float(row['estimated_cost']),
                    "latency_ms": row['latency_ms'],
                    "metadata": row['metadata']
                }
                for row in cur.fetchall()
            ]
