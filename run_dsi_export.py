import argparse
import asyncio
import csv
import os
from typing import Dict, List, Any

from app.core.config import get_settings
from app.core.database import db_pool
from app.services.metrics.simplified_dsi_calculator import SimplifiedDSICalculator


def write_csv(path: str, rows: List[Dict[str, Any]]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if not rows:
        with open(path, "w", newline="", encoding="utf-8") as f:
            f.write("")
        return
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
    parser = argparse.ArgumentParser(description="Export DSI CSVs")
    parser.add_argument("--pipeline", required=True, help="Pipeline execution ID")
    args = parser.parse_args()

    settings = get_settings()
    pipeline_id = args.pipeline

    # Where to write inside the container
    exports_root = os.path.join(os.getcwd(), "exports", f"dsi_{pipeline_id[:8]}")
    os.makedirs(exports_root, exist_ok=True)

    calc = SimplifiedDSICalculator(settings, db_pool)
    calc.current_pipeline_id = pipeline_id

    print(f"Exporting DSI data for pipeline: {pipeline_id}")

    # Component outputs
    organic = await calc._calculate_organic_dsi()
    news = await calc._calculate_news_dsi()
    youtube = await calc._calculate_youtube_dsi()

    write_csv(os.path.join(exports_root, "organic_dsi.csv"), organic)
    write_csv(os.path.join(exports_root, "news_dsi.csv"), news)
    write_csv(os.path.join(exports_root, "youtube_dsi.csv"), youtube)

    # Stored scores snapshot
    async with db_pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT 
              pipeline_execution_id, company_domain, dsi_score,
              keyword_overlap_score, content_relevance_score,
              market_presence_score, traffic_share_score, serp_visibility_score,
              created_at, updated_at,
              (metadata->>'source') as source
            FROM dsi_scores
            WHERE pipeline_execution_id = $1
            ORDER BY dsi_score DESC
            """,
            pipeline_id,
        )
    write_csv(os.path.join(exports_root, "dsi_scores.csv"), [dict(r) for r in rows])

    print(f"Export complete → {exports_root}")


if __name__ == "__main__":
    asyncio.run(main())


