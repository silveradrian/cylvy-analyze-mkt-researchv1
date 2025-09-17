import argparse
import asyncio
import csv
import os
from typing import Any, Dict, List

from app.core.config import get_settings
from app.core.database import db_pool


def write_csv(path: str, rows: List[Dict[str, Any]]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if not rows:
        # still create headers from nothing
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
        w = csv.DictWriter(f, fieldnames=headers, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)


async def export(pipeline_id: str) -> None:
    # 1) Export consolidated dsi_scores
    async with db_pool.acquire() as conn:
        dsi_rows = await conn.fetch(
            """
            SELECT 
              pipeline_execution_id, company_domain, dsi_score,
              keyword_overlap_score, content_relevance_score,
              market_presence_score, traffic_share_score, serp_visibility_score,
              created_at, updated_at,
              (metadata->>'source') AS source
            FROM dsi_scores
            WHERE pipeline_execution_id = $1
            ORDER BY dsi_score DESC
            """,
            pipeline_id,
        )
    dsi_dicts = [dict(r) for r in dsi_rows]
    write_csv(os.path.join("exports", f"dsi_scores_{pipeline_id[:8]}.csv"), dsi_dicts)

    # 2) Export page snapshots (all sources)
    async with db_pool.acquire() as conn:
        page_rows = await conn.fetch(
            """
            SELECT *
            FROM historical_page_dsi_snapshots
            ORDER BY snapshot_date DESC, page_dsi_score DESC
            """
        )
    page_dicts = [dict(r) for r in page_rows]
    write_csv(os.path.join("exports", f"page_dsi_snapshots_{pipeline_id[:8]}.csv"), page_dicts)


def main() -> None:
    parser = argparse.ArgumentParser(description="Export DSI CSVs")
    parser.add_argument("--pipeline", required=True, help="Pipeline execution ID")
    args = parser.parse_args()
    # ensure settings init (even if not directly used)
    _ = get_settings()
    asyncio.run(export(args.pipeline))
    print("CSV exports written to exports/")


if __name__ == "__main__":
    main()


