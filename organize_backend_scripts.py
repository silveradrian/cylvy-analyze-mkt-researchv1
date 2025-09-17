#!/usr/bin/env python3
"""
Organize backend folder by moving all non-essential scripts to appropriate subfolders
"""

import os
import shutil
from pathlib import Path

def organize_backend_scripts():
    """Organize backend scripts into appropriate categories"""
    
    print('📁 ORGANIZING BACKEND SCRIPTS')
    print('=' * 30)
    
    backend_path = Path('backend')
    
    # Define script categories with their patterns
    script_categories = {
        'backend/scripts/tests/': [
            'test_*.py',
            'quick_*_test.py'
        ],
        'backend/scripts/checks/': [
            'check_*.py',
            'audit_*.py',
            'monitor_*.py'
        ],
        'backend/scripts/fixes/': [
            'fix_*.py',
            'restart_*.py',
            'resume_*.py'
        ],
        'backend/scripts/exports/': [
            '*.csv',
            '*.xlsx',
            'export_*.py',
            'create_accurate_*.py',
            'create_correct_*.py',
            'create_working_*.py',
            'working_dsi_*.csv'
        ],
        'backend/scripts/debug/': [
            'debug_*.py',
            'diagnose_*.py',
            'investigate_*.py',
            'simple_*_debug.py'
        ],
        'backend/scripts/utilities/': [
            'purge_*.py',
            'populate_*.py',
            'complete_*.py',
            'comprehensive_*.py',
            'enhance_*.py',
            'enrich_*.py',
            'continue_*.py',
            'calculate_*.py',
            'remove_*.py',
            'clear_*.py',
            'queue_*.py',
            'integrate_*.py',
            'domain_normalization_*.py',
            'final_*.py'
        ]
    }
    
    moved_count = 0
    skipped_count = 0
    protected_files = set()
    
    # Files that should stay in backend root (essential)
    essential_files = {
        'app/',  # Core application 
        'migrations/',  # Database migrations
        'tests/',  # Core tests
        'logs/',  # Log directories
        'storage/',  # Storage directories
        'legacy_scripts/',  # Already organized
        'redundant/',  # Already organized
        'scripts/',  # Script directories
        'requirements.txt',  # Dependencies
        'Dockerfile',  # Docker build
        'main.py.patch',  # Core patches
        'pipeline_manager.py',  # Core pipeline manager
        'production_preflight_check.py',  # Essential production tool
        'setup_project_data.py',  # Essential setup
        'strategic_imperatives_reanalysis.py'  # Important analysis (has SQL error to fix)
    }
    
    # Move files by category
    for destination, patterns in script_categories.items():
        print(f'\n📂 Moving files to {destination}:')
        
        # Ensure destination exists
        os.makedirs(destination, exist_ok=True)
        
        moved_in_category = 0
        
        for pattern in patterns:
            # Find matching files in backend directory
            if '*' in pattern:
                # Handle glob patterns
                matching_files = list(backend_path.glob(pattern))
            else:
                # Handle exact filenames
                file_path = backend_path / pattern
                matching_files = [file_path] if file_path.exists() else []
            
            for file_path in matching_files:
                filename = file_path.name
                
                # Skip if it's a protected/essential file
                if any(essential in str(file_path) for essential in essential_files):
                    protected_files.add(filename)
                    continue
                
                # Skip if it's a directory
                if file_path.is_dir():
                    continue
                
                try:
                    destination_path = Path(destination) / filename
                    
                    # Only move if not already there and source exists
                    if file_path.exists() and not destination_path.exists():
                        shutil.move(str(file_path), str(destination_path))
                        print(f'   ✅ Moved: {filename}')
                        moved_count += 1
                        moved_in_category += 1
                    elif destination_path.exists():
                        print(f'   ℹ️  Already exists: {filename}')
                        skipped_count += 1
                
                except Exception as e:
                    print(f'   ❌ Error moving {filename}: {str(e)[:40]}...')
                    skipped_count += 1
        
        if moved_in_category == 0:
            print(f'   ℹ️  No files moved to this category')
    
    # List remaining backend files for review
    print(f'\n📋 REMAINING BACKEND ROOT FILES:')
    
    remaining_files = []
    for item in backend_path.iterdir():
        if item.is_file() and not item.name.startswith('.') and item.name not in protected_files:
            remaining_files.append(item.name)
    
    if remaining_files:
        print(f'   Files that should be reviewed:')
        for filename in sorted(remaining_files):
            # Categorize remaining files
            if any(pattern in filename.lower() for pattern in ['test', 'check', 'debug', 'fix']):
                category = 'Should be moved'
                icon = '🔍'
            elif filename.endswith(('.csv', '.xlsx', '.txt')):
                category = 'Export/data file'
                icon = '📊'
            elif filename.endswith('.py'):
                category = 'Script - review needed'
                icon = '🐍'
            else:
                category = 'Other'
                icon = '📄'
            
            print(f'   {icon} {filename:40} ({category})')
    
    print(f'\n📊 BACKEND ORGANIZATION SUMMARY:')
    print(f'   ✅ Files moved: {moved_count}')
    print(f'   ⚠️  Files skipped: {skipped_count}')
    print(f'   🛡️  Protected files: {len(protected_files)}')
    
    print(f'\n🎯 BACKEND STRUCTURE NOW ORGANIZED:')
    print(f'   📂 Root: Essential files only (app/, requirements.txt, etc.)')
    print(f'   🧪 scripts/tests/: All test_*.py files')
    print(f'   🔍 scripts/checks/: All check_*.py and audit_*.py files')
    print(f'   🔧 scripts/fixes/: All fix_*.py and restart_*.py files')
    print(f'   📊 scripts/exports/: CSV exports and export scripts')
    print(f'   🐛 scripts/debug/: Debug and diagnostic scripts')
    print(f'   🛠️  scripts/utilities/: Utility scripts (purge, populate, etc.)')

if __name__ == "__main__":
    organize_backend_scripts()
