import argparse
import os
from collections import namedtuple
import re
from datetime import datetime
import shutil

args = argparse.ArgumentParser(description='Resolve Syncthing conflict files by keeping the most recent version.')
args.add_argument('path', help='Path to search for conflict files')
args.add_argument('--dry-run', action='store_true', help='Show what would be done without making any changes')
args = args.parse_args()

conflict_item = namedtuple('Conflict', ['conflict_path', 'file_path', 'timestamp'])

def main():
    re_conflict = re.compile(r'^.+\.sync-conflict-.+')
    re_timestamp = re.compile(r'sync-conflict-(\d{8})-(\d{6})-.*\.bak')
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
                    file_path = os.path.basename(file).split('.sync-conflict-')[0]
                    file_path = os.path.join(root, file_path)

                    conflict_files.append(conflict_item(conflict_path=conflict_path, file_path=file_path, timestamp=timestamp))

    # Sort conflict_files by timestamp in descending order
    conflict_files.sort(key=lambda x: x.timestamp, reverse=True)
    
    # Keep track of processed file paths to handle only the most recent conflict
    processed_files = set()
    
    # Determine terminal width with a fallback to 80
    terminal_width = shutil.get_terminal_size((80, 20)).columns
    max_filename_length = terminal_width - 50  # Adjust based on expected width of other columns
    
    # Prepare header
    header = f"{'Filename'.ljust(max_filename_length)} | {'Old Timestamp'.ljust(19)} | {'New Timestamp'.ljust(19)}"
    separator = '-' * len(header)
    
    print(header)
    print(separator)
    
    for conflict in conflict_files:
        # If we've already processed this file path, skip it
        if conflict.file_path in processed_files:
            continue
        
        # Mark this file path as processed
        processed_files.add(conflict.file_path)
        
        # Prepare data for the table
        old_timestamp = 'N/A'
        if os.path.exists(conflict.file_path):
            old_timestamp = datetime.fromtimestamp(os.path.getmtime(conflict.file_path)).strftime('%Y-%m-%d %H:%M:%S')
        
        new_timestamp = conflict.timestamp.strftime('%Y-%m-%d %H:%M:%S')
        filename = conflict.file_path
        
        # Trim the filename if necessary
        if len(filename) > max_filename_length:
            filename = '...' + filename[-(max_filename_length - 3):]
        
        # Print the row
        print(f"{filename.ljust(max_filename_length)} | {old_timestamp.ljust(19)} | {new_timestamp.ljust(19)}")

        if not args.dry_run and os.path.exists(conflict.conflict_path):
            os.rename(conflict.conflict_path, conflict.file_path) # Rename conflict file to its original name
            # This kills the original file and replaces it with the new conflict file


if __name__ == '__main__':
    main()