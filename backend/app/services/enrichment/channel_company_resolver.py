"""
Background resolver that enriches YouTube channels with company domain/name
separately from the main pipeline flow.

It periodically scans recent video_snapshots for channels missing a company domain
in youtube_channel_companies and resolves them using OpenAI in batches.
"""
from __future__ import annotations

import asyncio
import json
import re
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional

from loguru import logger

from app.core.config import Settings
from app.core.database import DatabasePool


class ChannelCompanyResolver:
    def __init__(self, db: DatabasePool, settings: Settings):
        self.db = db
        self.settings = settings
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._scan_interval_s = 20
        self._batch_size = getattr(settings, 'video_enricher_ai_batch_size', 20)

    def is_running(self) -> bool:
        return bool(self._task and not self._task.done())

    def start_background(self):
        if self.is_running():
            return
        self._task = asyncio.create_task(self._run_loop(), name="channel_company_resolver")
        logger.info("Started ChannelCompanyResolver background task")

    async def _run_loop(self):
        self._running = True
        try:
            while True:
                try:
                    pending = await self._fetch_pending_channel_ids()
                    if not pending:
                        await asyncio.sleep(self._scan_interval_s)
                        continue

                    logger.info(f"ChannelCompanyResolver: {len(pending)} pending channels to resolve")
                    # Process in batches
                    for i in range(0, len(pending), self._batch_size):
                        batch = pending[i:i + self._batch_size]
                        await self._resolve_batch(batch)
                        # short breather to avoid burst rate
                        await asyncio.sleep(0.2)
                except Exception as e:
                    logger.error(f"ChannelCompanyResolver loop error: {e}")
                    await asyncio.sleep(self._scan_interval_s)
        finally:
            self._running = False

    async def _fetch_pending_channel_ids(self) -> List[str]:
        """Return channel_ids from recent snapshots that lack company_domain."""
        try:
            async with self.db.acquire() as conn:
                rows = await conn.fetch(
                    """
                    WITH recent_channels AS (
                        SELECT DISTINCT channel_id
                        FROM video_snapshots
                        WHERE snapshot_date >= CURRENT_DATE - INTERVAL '2 days'
                    )
                    SELECT rc.channel_id
                    FROM recent_channels rc
                    LEFT JOIN youtube_channel_companies ycc
                        ON ycc.channel_id = rc.channel_id
                    WHERE ycc.channel_id IS NULL  -- Only truly unprocessed channels
                    LIMIT 500
                    """
                )
                return [r['channel_id'] for r in rows]
        except Exception as e:
            logger.error(f"ChannelCompanyResolver pending fetch error: {e}")
            return []

    async def _resolve_batch(self, channel_ids: List[str]):
        # Fetch channel snippets/descriptions to provide context
        channel_stats = await self._fetch_channel_context(channel_ids)
        if not channel_stats:
            return
        results = await self._extract_domains_batch(channel_stats)
        if results:
            await self._store_channel_domains_batch(results)

    async def _fetch_channel_context(self, channel_ids: List[str]) -> Dict[str, Dict]:
        """Get minimal context for channels from existing data (snapshots); fallback to blanks."""
        try:
            async with self.db.acquire() as conn:
                # We may not have channel descriptions locally; keep minimal fields
                rows = await conn.fetch(
                    """
                    SELECT DISTINCT channel_id, channel_title
                    FROM video_snapshots
                    WHERE channel_id = ANY($1)
                    """,
                    channel_ids
                )
                stats: Dict[str, Dict] = {}
                for r in rows:
                    stats[r['channel_id']] = {
                        'title': r['channel_title'] or '',
                        'subscriber_count': 0,
                        'description': ''
                    }
                return stats
        except Exception as e:
            logger.error(f"ChannelCompanyResolver fetch context error: {e}")
            return {}

    async def _extract_domains_batch(self, channel_stats: Dict[str, Dict]) -> Dict[str, Dict]:
        """Use OpenAI Responses API once per batch to resolve company domains."""
        if not self.settings.OPENAI_API_KEY:
            return {}
        try:
            from openai import OpenAI
            client = OpenAI(api_key=self.settings.OPENAI_API_KEY)

            channels = list(channel_stats.items())
            # Build prompt
            ctx_lines: List[str] = []
            for idx, (cid, data) in enumerate(channels):
                title = data.get('title', '')
                description = (data.get('description', '') or '')[:2000]
                ctx_lines.append(f"""
Channel {idx+1}:
- ID: {cid}
- Title: {title}
- Description excerpt: {description}
""")
            prompt = f"""
Analyze the following YouTube channels and select the official company domain for each.
If unclear, return empty domain and company_name with low confidence.

Return a JSON array with: channel_index (1-based), domain, company_name, source_type, confidence (0-1).

Channels:
{chr(10).join(ctx_lines)}
"""

            # Call off the event loop with timeout
            import asyncio as _asyncio
            response = await _asyncio.wait_for(
                _asyncio.to_thread(
                    lambda: client.responses.create(
                        model=getattr(self.settings, 'video_enricher_ai_model', "gpt-4.1-nano-2025-04-14"),
                        input=[
                            {"role": "system", "content": "Extract official company domains for channels. Return strict JSON."},
                            {"role": "user", "content": prompt}
                        ],
                        # Some client versions do not accept max_completion_tokens; omit for compatibility
                    )
                ),
                timeout=getattr(self.settings, 'video_enricher_ai_timeout_s', 30)
            )
            content = getattr(response, 'output_text', '')
            if not content:
                return {}
            try:
                data = json.loads(content)
            except Exception:
                # Try to salvage
                s = content.find('['); e = content.rfind(']')
                if s != -1 and e > s:
                    data = json.loads(content[s:e+1])
                else:
                    s = content.find('{'); e = content.rfind('}')
                    data = json.loads(content[s:e+1])

            if isinstance(data, dict) and 'channels' in data:
                data = data['channels']

            results: Dict[str, Dict] = {}
            # Initialize all channels with empty results
            for channel_id, _ in channels:
                results[channel_id] = {
                    'company_domain': '',
                    'company_name': '',
                    'source_type': 'NO_DOMAIN_FOUND',
                    'confidence': 0.0,
                }
            
            # Update with AI-extracted results
            for i, item in enumerate(data):
                idx = int(item.get('channel_index', 0)) - 1
                if 0 <= idx < len(channels):
                    channel_id = channels[idx][0]
                    domain = (item.get('domain', '') or '').lower().strip()
                    if domain:
                        domain = domain.replace('http://', '').replace('https://', '')
                        domain = domain.replace('www.', '').split('/')[0]
                    results[channel_id] = {
                        'company_domain': domain,
                        'company_name': item.get('company_name', ''),
                        'source_type': item.get('source_type', 'OTHER') if domain else 'NO_DOMAIN_FOUND',
                        'confidence': float(item.get('confidence', 0.5)) if domain else 0.0,
                    }
            return results
        except Exception as e:
            logger.error(f"ChannelCompanyResolver AI batch error: {e}")
            # Return empty results for all channels on error
            return {
                channel_id: {
                    'company_domain': '',
                    'company_name': '',
                    'source_type': 'EXTRACTION_ERROR',
                    'confidence': 0.0,
                }
                for channel_id, _ in channels
            }

    async def _store_channel_domains_batch(self, results: Dict[str, Dict]):
        if not results:
            return
        try:
            async with self.db.acquire() as conn:
                values = []
                # Process channels with found domains
                for cid, data in results.items():
                    if data.get('company_domain'):
                        values.append((
                            cid,
                            data.get('company_domain', ''),
                            data.get('company_name', ''),
                            data.get('source_type', 'OTHER'),
                            data.get('confidence', 0.0),
                            datetime.utcnow()
                        ))
                    else:
                        # Mark channels with no domain found as processed with empty domain
                        values.append((
                            cid,
                            '',  # empty domain
                            '',  # empty company name
                            'NO_DOMAIN_FOUND',
                            0.0,
                            datetime.utcnow()
                        ))
                
                if not values:
                    return
                await conn.executemany(
                    """
                    INSERT INTO youtube_channel_companies (
                        channel_id, company_domain, company_name, source_type,
                        confidence_score, extracted_at, created_at
                    ) VALUES ($1, $2, $3, $4, $5, $6, NOW())
                    ON CONFLICT (channel_id) DO UPDATE SET
                        company_domain = EXCLUDED.company_domain,
                        company_name = EXCLUDED.company_name,
                        source_type = EXCLUDED.source_type,
                        confidence_score = EXCLUDED.confidence_score,
                        extracted_at = EXCLUDED.extracted_at,
                        updated_at = NOW()
                    """,
                    values
                )
                logger.info(f"ChannelCompanyResolver: stored {len(values)} channel domains")
        except Exception as e:
            logger.error(f"ChannelCompanyResolver store error: {e}")


