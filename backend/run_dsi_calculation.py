import argparse
import asyncio
from typing import Optional

from app.core.config import get_settings
from app.core.database import db_pool
from app.services.metrics.simplified_dsi_calculator import SimplifiedDSICalculator


async def run_dsi(pipeline_id: Optional[str]) -> int:
    settings = get_settings()
    calc = SimplifiedDSICalculator(settings, db_pool)

    print("Starting DSI calculation...", flush=True)
    try:
        result = await calc.calculate_dsi_rankings(pipeline_id)

        def count(key: str) -> int:
            value = result.get(key)
            if isinstance(value, list):
                return len(value)
            return int(value or 0)

        print("\n=== DSI SUMMARY ===", flush=True)
        print(f"Companies ranked: {result.get('companies_ranked', 0)}", flush=True)
        print(f"Pages ranked: {result.get('pages_ranked', 0)}", flush=True)
        print(f"Organic items: {count('organic_dsi')}", flush=True)
        print(f"News items: {count('news_dsi')}", flush=True)
        print(f"YouTube items: {count('youtube_dsi')}", flush=True)

        def preview(items_key: str, label: str) -> None:
            items = result.get(items_key, []) or []
            print(f"\nTop {label} (up to 5):", flush=True)
            for idx, item in enumerate(items[:5], 1):
                company = item.get('company_name') or item.get('domain') or 'Unknown'
                score = item.get('dsi_score') or item.get('news_dsi_score') or item.get('video_dsi_score') or 0
                print(f" {idx}. {company} — score={score}", flush=True)

        preview('organic_dsi', 'Organic')
        preview('news_dsi', 'News')
        preview('youtube_dsi', 'YouTube')

        return 0
    except Exception as e:
        print(f"DSI calculation failed: {e}", flush=True)
        return 1


def main() -> None:
    parser = argparse.ArgumentParser(description="Run DSI calculations")
    parser.add_argument("--pipeline", dest="pipeline_id", default=None, help="Pipeline execution ID")
    args = parser.parse_args()

    exit_code = asyncio.run(run_dsi(args.pipeline_id))
    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()


