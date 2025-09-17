#!/usr/bin/env python
"""
Pipeline Manager - Comprehensive tool for pipeline management with robustness and transparency
"""
import asyncio
import sys
from datetime import datetime
from typing import Optional, Dict, Any
from uuid import UUID
import click
# from tabulate import tabulate
from loguru import logger

from app.core.database import db_pool
from app.core.config import settings
from app.services.pipeline.pipeline_service import PipelineService, PipelineConfig
from app.services.analysis.concurrent_content_analyzer import ConcurrentContentAnalyzer


async def get_pipeline_status(pipeline_id: str) -> Dict[str, Any]:
    """Get comprehensive pipeline status"""
    async with db_pool.acquire() as conn:
        # Find pipeline by ID prefix
        pipeline = await conn.fetchrow("""
            SELECT * FROM pipeline_executions
            WHERE id::text LIKE $1 || '%'
            ORDER BY started_at DESC
            LIMIT 1
        """, pipeline_id)
        
        if not pipeline:
            return None
            
        # Get phase statuses
        phases = await conn.fetch("""
            SELECT phase_name, status, started_at, completed_at,
                   EXTRACT(EPOCH FROM (COALESCE(completed_at, NOW()) - started_at)) as duration_seconds
            FROM pipeline_phase_status
            WHERE pipeline_execution_id = $1
            ORDER BY started_at
        """, pipeline['id'])
        
        # Get content analysis details
        content_stats = await conn.fetchrow("""
            SELECT 
                COUNT(DISTINCT sc.url) as total_scraped,
                COUNT(DISTINCT CASE WHEN cd.domain IS NOT NULL THEN sc.url END) as enriched_content,
                COUNT(DISTINCT oca.url) as analyzed,
                COUNT(DISTINCT CASE 
                    WHEN sc.url IS NOT NULL 
                    AND sc.status = 'completed'
                    AND cd.domain IS NOT NULL
                    AND oca.url IS NULL 
                    THEN sc.url 
                END) as pending_analysis
            FROM scraped_content sc
            LEFT JOIN serp_results sr ON sr.url = sc.url AND sr.pipeline_execution_id = $1
            LEFT JOIN company_domains cd ON cd.domain = sr.domain
            LEFT JOIN optimized_content_analysis oca ON oca.url = sc.url
            WHERE sr.pipeline_execution_id = $1
        """, pipeline['id'])
        
        return {
            'pipeline': dict(pipeline),
            'phases': [dict(p) for p in phases],
            'content_stats': dict(content_stats) if content_stats else {}
        }


async def fix_stuck_phase(pipeline_id: str, phase_name: str):
    """Fix a stuck phase by resetting its status"""
    async with db_pool.acquire() as conn:
        result = await conn.fetchrow("""
            UPDATE pipeline_phase_status
            SET status = 'running', 
                started_at = COALESCE(started_at, NOW()), 
                updated_at = NOW()
            WHERE pipeline_execution_id::text LIKE $1 || '%'
            AND phase_name = $2
            AND status IN ('pending', 'failed', 'blocked')
            RETURNING *
        """, pipeline_id, phase_name)
        
        if result:
            logger.info(f"Reset phase {phase_name} to running status")
            return True
        return False


async def start_content_analyzer(pipeline_id: str):
    """Manually start content analyzer for a pipeline"""
    # Find full pipeline ID
    async with db_pool.acquire() as conn:
        full_id = await conn.fetchval("""
            SELECT id FROM pipeline_executions
            WHERE id::text LIKE $1 || '%'
            LIMIT 1
        """, pipeline_id)
        
        if not full_id:
            logger.error(f"Pipeline {pipeline_id} not found")
            return False
    
    # Start analyzer
    analyzer = ConcurrentContentAnalyzer(settings, db_pool)
    logger.info(f"Starting content analyzer for pipeline {full_id}")
    
    # Run for a limited time
    task = asyncio.create_task(analyzer.start_monitoring(str(full_id), project_id=None))
    await asyncio.sleep(60)  # Run for 1 minute
    await analyzer.stop_monitoring()
    
    stats = await analyzer.get_analysis_stats()
    logger.info(f"Analyzer stats: {stats}")
    return True


@click.group()
def cli():
    """Pipeline Manager CLI"""
    pass


@cli.command()
@click.argument('pipeline_id')
def status(pipeline_id: str):
    """Get comprehensive pipeline status"""
    async def _status():
        await db_pool.initialize()
        
        data = await get_pipeline_status(pipeline_id)
        if not data:
            click.echo(f"Pipeline {pipeline_id} not found")
            return
            
        pipeline = data['pipeline']
        phases = data['phases']
        content_stats = data['content_stats']
        
        # Pipeline summary
        runtime = (datetime.utcnow() - pipeline['started_at'].replace(tzinfo=None)).total_seconds() / 60
        click.echo(f"\n=== PIPELINE {pipeline['id']} ===")
        click.echo(f"Status: {pipeline['status']}")
        click.echo(f"Runtime: {runtime:.1f} minutes")
        click.echo(f"Keywords: {pipeline['keywords_processed']}")
        click.echo(f"SERP Results: {pipeline['serp_results_collected']}")
        
        # Phase status table
        phase_data = []
        for phase in phases:
            duration = phase['duration_seconds'] / 60 if phase['duration_seconds'] else 0
            phase_data.append([
                phase['phase_name'],
                phase['status'],
                f"{duration:.1f} min" if phase['started_at'] else "-"
            ])
        
        click.echo("\n=== PHASE STATUS ===")
        click.echo(f"{'Phase':<30} {'Status':<15} {'Duration':<15}")
        click.echo("-" * 60)
        for row in phase_data:
            click.echo(f"{row[0]:<30} {row[1]:<15} {row[2]:<15}")
        
        # Content analysis details
        if content_stats:
            click.echo(f"\n=== CONTENT ANALYSIS ===")
            click.echo(f"Total scraped: {content_stats['total_scraped']}")
            click.echo(f"Enriched: {content_stats['enriched_content']}")
            click.echo(f"Analyzed: {content_stats['analyzed']}")
            click.echo(f"Pending: {content_stats['pending_analysis']}")
    
    asyncio.run(_status())


@cli.command()
@click.argument('pipeline_id')
@click.argument('phase_name')
def fix_phase(pipeline_id: str, phase_name: str):
    """Fix a stuck phase"""
    async def _fix():
        await db_pool.initialize()
        
        success = await fix_stuck_phase(pipeline_id, phase_name)
        if success:
            click.echo(f"✅ Successfully reset {phase_name} phase")
        else:
            click.echo(f"❌ Failed to reset {phase_name} phase")
    
    asyncio.run(_fix())


@cli.command()
@click.argument('pipeline_id')
def analyze(pipeline_id: str):
    """Start content analyzer for a pipeline"""
    async def _analyze():
        await db_pool.initialize()
        
        success = await start_content_analyzer(pipeline_id)
        if success:
            click.echo("✅ Content analyzer completed")
        else:
            click.echo("❌ Content analyzer failed")
    
    asyncio.run(_analyze())


@cli.command()
def list_pipelines():
    """List recent pipelines"""
    async def _list():
        await db_pool.initialize()
        
        async with db_pool.acquire() as conn:
            pipelines = await conn.fetch("""
                SELECT id, status, mode, started_at,
                       keywords_processed, serp_results_collected, content_analyzed
                FROM pipeline_executions
                ORDER BY started_at DESC
                LIMIT 10
            """)
            
            data = []
            for p in pipelines:
                runtime = (datetime.utcnow() - p['started_at'].replace(tzinfo=None)).total_seconds() / 60
                data.append([
                    str(p['id'])[:8],
                    p['status'],
                    p['mode'],
                    f"{runtime:.1f} min",
                    p['keywords_processed'],
                    p['serp_results_collected'],
                    p['content_analyzed']
                ])
            
            click.echo("\n=== RECENT PIPELINES ===")
            click.echo(f"{'ID':<10} {'Status':<12} {'Mode':<15} {'Runtime':<12} {'Keywords':<10} {'SERP':<10} {'Analyzed':<10}")
            click.echo("-" * 90)
            for row in data:
                click.echo(f"{row[0]:<10} {row[1]:<12} {row[2]:<15} {row[3]:<12} {row[4]:<10} {row[5]:<10} {row[6]:<10}")
    
    asyncio.run(_list())


if __name__ == '__main__':
    cli()
