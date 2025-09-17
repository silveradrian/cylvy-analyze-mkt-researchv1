#!/usr/bin/env python3
"""
Organize project files by moving non-essential scripts to scripts folder
"""

import os
import shutil
from pathlib import Path

def organize_project_files():
    """Organize project files into appropriate folders"""
    
    print('📁 ORGANIZING PROJECT FILES')
    print('=' * 30)
    
    # Define file categories
    file_moves = {
        'scripts/exports/': [
            # CSV exports
            'accurate_us_organic_dsi.csv',
            'enhanced_us_organic_dsi.csv', 
            'final_corrected_us_organic_dsi.csv',
            'final_realistic_corrected_dsi.csv',
            'final_realistic_dsi.csv',
            'organic_dsi_by_country.csv',
            'robust_us_organic_dsi.csv',
            'top500_domain_analysis.csv',
            # Excel exports
            'digital_landscape_b15f3497_20250914_141146.xlsx',
            'pipeline_export_fixed.xlsx',
            'pipeline_export.xlsx',
        ],
        'scripts/logs/': [
            'backend_full_logs.txt',
            'backend_logs.txt',
            'error_logs.txt',
            'keyword_phase_logs.txt',
            'pipeline_logs.txt',
            'pipeline_start_logs.txt',
            'recent_logs.txt',
            'temp_logs.txt',
        ],
        'scripts/analysis/': [
            'monitor_finastra_system.py',
            'updated_jtbd_config.sql',
        ],
        'scripts/docs/': [
            'DASHBOARD_READINESS_ASSESSMENT.md',
            'FRONTEND_DASHBOARD_DATA_DICTIONARY.md',
            'PIPELINE_ROBUSTNESS_ANALYSIS.md',
            'SCRAPING_OPTIMIZATION_SUMMARY.md',
        ]
    }
    
    moved_count = 0
    skipped_count = 0
    
    # Move files by category
    for destination, files in file_moves.items():
        print(f'\n📂 Moving files to {destination}:')
        
        # Ensure destination exists
        os.makedirs(destination, exist_ok=True)
        
        for filename in files:
            if os.path.exists(filename):
                try:
                    destination_path = os.path.join(destination, filename)
                    # Only move if not already there
                    if not os.path.exists(destination_path):
                        shutil.move(filename, destination_path)
                        print(f'   ✅ Moved: {filename}')
                        moved_count += 1
                    else:
                        print(f'   ℹ️  Already exists: {filename}')
                        skipped_count += 1
                except Exception as e:
                    print(f'   ❌ Error moving {filename}: {str(e)[:50]}...')
                    skipped_count += 1
            else:
                print(f'   ⚠️  Not found: {filename}')
    
    # Check for additional CSV/Excel files that might have been created
    print(f'\n🔍 Checking for additional export files...')
    
    root_path = Path('.')
    additional_exports = []
    
    for file_path in root_path.glob('*.csv'):
        if file_path.name not in [item for sublist in file_moves.values() for item in sublist]:
            additional_exports.append(file_path.name)
    
    for file_path in root_path.glob('*.xlsx'):
        if file_path.name not in [item for sublist in file_moves.values() for item in sublist]:
            additional_exports.append(file_path.name)
    
    if additional_exports:
        print(f'   📊 Found {len(additional_exports)} additional export files:')
        for export_file in additional_exports:
            try:
                destination_path = os.path.join('scripts/exports/', export_file)
                if not os.path.exists(destination_path) and os.path.exists(export_file):
                    shutil.move(export_file, destination_path)
                    print(f'   ✅ Moved: {export_file}')
                    moved_count += 1
                else:
                    print(f'   ℹ️  Skipped: {export_file}')
                    skipped_count += 1
            except Exception as e:
                print(f'   ❌ Error: {export_file} - {str(e)[:30]}...')
                skipped_count += 1
    
    # List remaining root files for review
    print(f'\n📋 REMAINING ROOT FILES:')
    
    remaining_files = []
    for item in os.listdir('.'):
        if os.path.isfile(item) and not item.startswith('.'):
            remaining_files.append(item)
    
    if remaining_files:
        print(f'   Essential files that should stay in root:')
        essential_patterns = ['README', 'Makefile', 'docker-compose', 'DEPLOYMENT', 'PIPELINE_MASTER', 'finastra_keywords.csv']
        
        for filename in sorted(remaining_files):
            is_essential = any(pattern in filename for pattern in essential_patterns)
            icon = '✅' if is_essential else '🔍'
            category = 'Essential' if is_essential else 'Review needed'
            print(f'   {icon} {filename:40} ({category})')
    
    print(f'\n📊 ORGANIZATION SUMMARY:')
    print(f'   ✅ Files moved: {moved_count}')
    print(f'   ⚠️  Files skipped: {skipped_count}')
    print(f'   📁 Folders created: scripts/exports, scripts/logs, scripts/analysis, scripts/docs')
    
    print(f'\n🎯 PROJECT STRUCTURE NOW ORGANIZED:')
    print(f'   📂 Root: Essential files only (docker-compose, README, etc.)')
    print(f'   📊 scripts/exports/: CSV and Excel export files')
    print(f'   📋 scripts/logs/: Log files and debugging output')
    print(f'   🔧 scripts/analysis/: Analysis scripts and utilities')
    print(f'   📚 scripts/docs/: Analysis documentation and reports')

if __name__ == "__main__":
    organize_project_files()
