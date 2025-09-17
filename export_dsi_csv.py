import asyncio
import csv
import os
from typing import Dict, List, Any

from app.core.config import get_settings
from app.core.database import db_pool
from app.services.metrics.simplified_dsi_calculator import SimplifiedDSICalculator


def _write_csv(path: str, rows: List[Dict[str, Any]]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if not rows:
        # Create empty file with no rows
        with open(path, "w", newline="", encoding="utf-8") as f:
            f.write("")
        return
    # Collect union of keys to ensure consistent headers
    headers: List[str] = []
    seen = set()
    for r in rows:
        for k in r.keys():
            if k not in seen:
                headers.append(k)
                seen.add(k)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=headers, extrasaction="ignore")
        writer.writeheader()
        for r in rows:
            writer.writerow(r)


async def main() -> None:
    settings = get_settings()
    pipeline_id = os.environ.get("PIPELINE_ID", "")
    if not pipeline_id:
        # Default to latest running or require explicit
        raise SystemExit("PIPELINE_ID env var is required")

    exports_dir = os.path.join(os.getcwd(), "exports")
    os.makedirs(exports_dir, exist_ok=True)

    calc = SimplifiedDSICalculator(settings, db_pool)
    calc.current_pipeline_id = pipeline_id

    print(f"Exporting DSI data for pipeline: {pipeline_id}")

    # 1) Run component queries (without storing) and export raw outputs
    organic = await calc._calculate_organic_dsi()
    news = await calc._calculate_news_dsi()
    youtube = await calc._calculate_youtube_dsi()

    _write_csv(os.path.join(exports_dir, f"organic_dsi_{pipeline_id[:8]}.csv"), organic)
    _write_csv(os.path.join(exports_dir, f"news_dsi_{pipeline_id[:8]}.csv"), news)
    _write_csv(os.path.join(exports_dir, f"youtube_dsi_{pipeline_id[:8]}.csv"), youtube)

    # 2) Export stored scores table (if any rows exist)
    async with db_pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT 
              pipeline_execution_id, company_domain, dsi_score,
              keyword_overlap_score, content_relevance_score,
              market_presence_score, traffic_share_score, serp_visibility_score,
              created_at, updated_at
            FROM dsi_scores
            WHERE pipeline_execution_id = $1
            ORDER BY dsi_score DESC
            """,
            pipeline_id,
        )
        stored = [dict(r) for r in rows]
    _write_csv(os.path.join(exports_dir, f"dsi_scores_{pipeline_id[:8]}.csv"), stored)

    print("Export complete:")
    for name in ("organic_dsi", "news_dsi", "youtube_dsi", "dsi_scores"):
        path = os.path.join(exports_dir, f"{name}_{pipeline_id[:8]}.csv")
        size = os.path.getsize(path) if os.path.exists(path) else 0
        print(f" - {os.path.basename(path)} ({size} bytes)")


if __name__ == "__main__":
    asyncio.run(main())


