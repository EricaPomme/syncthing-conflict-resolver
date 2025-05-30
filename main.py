import argparse
import os
from collections import namedtuple
import re
from datetime import datetime
import shutil

args = argparse.ArgumentParser(description='Resolve Syncthing conflict files by keeping the most recent version.')
args.add_argument('path', help='Path to search for conflict files')
args.add_argument('--dry-run', action='store_true', help='Show what would be done without making any changes')
args.add_argument('--backup-dir', help='Directory to move older conflict files to (if not provided, older conflicts will be deleted)')
args = args.parse_args()

conflict_item = namedtuple('Conflict', ['conflict_path', 'file_path', 'timestamp'])

# Constants for action types
ACTION_KEEP = 'keep'
ACTION_DELETE = 'delete'
ACTION_BACKUP = 'backup'

def main():
    re_conflict = re.compile(r'^.+\.sync-conflict-.+')
    re_timestamp = re.compile(r'sync-conflict-(\d{8})-(\d{6})-[A-Z0-9]+')
    # Walk provided path, get all files matching "\.sync-conflict-.*"
    conflict_files = []
    for root, _, files in os.walk(args.path):
        for file in files:
            if re_conflict.match(file):
                # Discard zero-length files (bad syncs)
                if os.path.getsize(os.path.join(root, file)) == 0:
                    continue
                
                # Extract timestamp from file name and convert to datetime object
                match = re_timestamp.search(file)
                if match:
                    date_str = match.group(1)  # YYYYMMDD
                    time_str = match.group(2)  # HHMMSS
                    timestamp = datetime.strptime(f"{date_str} {time_str}", "%Y%m%d %H%M%S")
                    
                    # Create a conflict namedtuple and add to the list
                    conflict_path = os.path.join(root, file)
                    
                    # Handle filenames with multiple extensions (e.g., file.txt.sync-conflict-...)
                    base_name = os.path.basename(file)
                    original_parts = base_name.split('.sync-conflict-')
                    
                    # Get the original filename with proper extension
                    if len(original_parts) > 1:
                        file_name = original_parts[0]
                        # Check if there's an extension after the random identifier (XXXXX.extension)
                        match_ext = re.search(r'[A-Z0-9]+\.(.+)$', original_parts[1])
                        if match_ext:
                            # Remove the extension from the conflict and use it for the original
                            file_name = file_name
                            
                    file_path = os.path.join(root, file_name)

                    conflict_files.append(conflict_item(conflict_path=conflict_path, file_path=file_path, timestamp=timestamp))

    # Group conflicts by file_path
    conflicts_by_path = {}
    for conflict in conflict_files:
        if conflict.file_path not in conflicts_by_path:
            conflicts_by_path[conflict.file_path] = []
        conflicts_by_path[conflict.file_path].append(conflict)
    
    # Sort each group by timestamp (newest first)
    for file_path, conflicts in conflicts_by_path.items():
        conflicts.sort(key=lambda x: x.timestamp, reverse=True)
    
    # Create a list of actions to perform
    actions = []
    for file_path, conflicts in conflicts_by_path.items():
        # The newest conflict replaces the original file
        newest_conflict = conflicts[0]
        original_timestamp = 'N/A'
        if os.path.exists(file_path):
            original_timestamp = datetime.fromtimestamp(os.path.getmtime(file_path)).strftime('%Y-%m-%d %H:%M:%S')
        
        actions.append({
            'conflict': newest_conflict,
            'action': ACTION_KEEP,
            'original_timestamp': original_timestamp
        })
        
        # Older conflicts either go to backup or get deleted
        for conflict in conflicts[1:]:
            if args.backup_dir:
                actions.append({
                    'conflict': conflict,
                    'action': ACTION_BACKUP,
                    'original_timestamp': original_timestamp
                })
            else:
                actions.append({
                    'conflict': conflict,
                    'action': ACTION_DELETE,
                    'original_timestamp': original_timestamp
                })
    
    # Fixed widths for action and timestamps
    action_width = 10
    timestamp_width = 19
    
    # Try to get terminal width, fallback to 120 if not available
    try:
        terminal_width = shutil.get_terminal_size((120, 20)).columns
    except Exception:
        terminal_width = 120
    
    # Calculate space needed for other columns (including separators)
    other_columns_width = action_width + (timestamp_width * 2) + 9  # 9 for the " | " separators
    
    # Allocate remaining space to filename, with a minimum width of 40
    filename_width = max(40, terminal_width - other_columns_width)
    
    # Format column headers with dynamic filename width
    header_format = f"{{:<{filename_width}}} | {{:<{action_width}}} | {{:<{timestamp_width}}} | {{:<{timestamp_width}}}"
    row_format = header_format  # Use same format for data rows
    
    # Print header
    print(header_format.format("Filename", "Action", "Original Time", "Conflict Time"))
    
    # Print separator line that matches header width exactly
    separator_width = filename_width + other_columns_width
    print("-" * separator_width)
    
    # Process all actions
    for action_info in actions:
        conflict = action_info['conflict']
        action_type = action_info['action']
        original_timestamp = action_info['original_timestamp']
        conflict_timestamp = conflict.timestamp.strftime('%Y-%m-%d %H:%M:%S')
        
        # Get display action text
        if action_type == ACTION_KEEP:
            action_text = "KEEP"
        elif action_type == ACTION_DELETE:
            action_text = "DELETE"
        else:  # ACTION_BACKUP
            action_text = "BACKUP"
        
        # Get the filename, truncate from left if too long
        filename = conflict.conflict_path
        if len(filename) > filename_width:
            filename = "..." + filename[-(filename_width-3):]
        
        # Print the row with all columns properly aligned
        print(row_format.format(filename, action_text, original_timestamp, conflict_timestamp))
        
        # Perform the action if not in dry run mode
        if not args.dry_run:
            if action_type == ACTION_KEEP and os.path.exists(conflict.conflict_path):
                os.rename(conflict.conflict_path, conflict.file_path)  # Rename conflict file to its original name
            elif action_type == ACTION_DELETE and os.path.exists(conflict.conflict_path):
                os.remove(conflict.conflict_path)  # Delete older conflict file
            elif action_type == ACTION_BACKUP and os.path.exists(conflict.conflict_path):
                # Create backup directory if it doesn't exist
                if not os.path.exists(args.backup_dir):
                    os.makedirs(args.backup_dir, exist_ok=True)
                
                # Create backup filename with timestamp to make it unique
                backup_filename = os.path.basename(conflict.conflict_path)
                backup_path = os.path.join(args.backup_dir, backup_filename)
                
                # Move the conflict file to backup directory
                shutil.move(conflict.conflict_path, backup_path)


if __name__ == '__main__':
    main()