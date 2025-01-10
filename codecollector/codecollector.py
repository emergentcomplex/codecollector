#!/usr/bin/env python3

import os
import argparse
from pathlib import Path
import re

def collect_files(start_dir, extensions, exclude_dirs):
    """Collect files recursively from start_dir if they match the given extensions, excluding specified directories."""
    collected = []
    start_dir = Path(start_dir).resolve()
    for root, dirs, files in os.walk(start_dir):
        # Modify dirs in-place to exclude specified directories
        dirs[:] = [d for d in dirs if d not in exclude_dirs]
        for file in files:
            if file.lower().endswith(extensions):
                full_path = Path(root) / file
                collected.append(full_path)
    return collected

def is_import_line(line, file_extension):
    """
    Determines if a line is an import statement based on the file extension.
    Excluded lines are not written to the output file.
    """
    import_patterns = {
        '.kt': re.compile(r'^\s*import\s+[\w.]+'),
        '.kts': re.compile(r'^\s*import\s+[\w.]+'),
        '.java': re.compile(r'^\s*import\s+[\w.]+;'),
        '.js': re.compile(r'^\s*import\s+.*\s+from\s+.*;?'),
        '.ts': re.compile(r'^\s*import\s+.*\s+from\s+.*;?'),
        '.svelte': re.compile(r'<script[^>]*>\s*import\s+.*\s+from\s+.*;\s*</script>'),
        # No patterns for .gradle, .xml, .toml, etc. since they're removed from default collection
    }
    
    pattern = import_patterns.get(file_extension, None)
    if pattern:
        return bool(pattern.match(line))
    return False

def get_tree_lines(start_dir, exclude_dirs, prefix=""):
    """Generate an ASCII tree representation of the directory structure, excluding specified directories."""
    start_path = Path(start_dir).resolve()
    if not start_path.is_dir():
        return [f"{start_path} is not a directory."]
    
    tree = []
    entries = sorted([e for e in start_path.iterdir() if e.name not in exclude_dirs], key=lambda e: (not e.is_dir(), e.name.lower()))
    entries_count = len(entries)
    for index, entry in enumerate(entries):
        connector = "└── " if index == entries_count - 1 else "├── "
        tree.append(f"{prefix}{connector}{entry.name}")
        if entry.is_dir():
            extension = "    " if index == entries_count - 1 else "│   "
            tree.extend(get_tree_lines(entry, exclude_dirs, prefix + extension))
    return tree

def write_output(collected_files, output_file, start_dir, exclude_dirs):
    with open(output_file, 'w', encoding='utf-8') as outfile:
        # 1. Write the folder structure
        tree_lines = get_tree_lines(start_dir, exclude_dirs)
        outfile.write("Folder Structure (ASCII Tree):\n")
        outfile.write("\n".join(tree_lines))
        
        if collected_files:
            # 2. Write the consolidated files
            outfile.write("\n\nConsolidated Code Files (Import statements excluded):\n")
            for file_path in collected_files:
                outfile.write(f"\n\n# File: {file_path}\n\n")
                try:
                    with open(file_path, 'r', encoding='utf-8') as infile:
                        for line in infile:
                            if not is_import_line(line, file_path.suffix):
                                outfile.write(line)
                except Exception as e:
                    outfile.write(f"<!-- Could not read file: {e} -->\n")
        else:
            outfile.write("\n\n[No files found with the specified extensions.]\n")

def parse_arguments():
    parser = argparse.ArgumentParser(
        description="Traverse directories, generate a tree of the structure, and consolidate code files, excluding import statements."
    )
    parser.add_argument(
        'start_dir',
        nargs='?',
        default='.',
        help='Top-level directory to start traversal (default: current directory)'
    )
    parser.add_argument(
        '-e', '--extensions',
        nargs='+',
        default=[
            '.kt',      # Kotlin
            '.kts',     # Kotlin script
            '.java',    # Java
            '.svelte',  # Svelte
            '.js',      # JavaScript
            '.ts',      # TypeScript
            '.html',    # HTML
            '.css',      # CSS
            '.py'       # Python
        ],
        help=(
            "List of file extensions to include (default: "
            ".kt .kts .java .svelte .js .ts .html .css .py)"
        )
    )
    parser.add_argument(
        '-o', '--output',
        default='codebase.prompt',
        help='Name of the output file (default: codebase.prompt)'
    )
    parser.add_argument(
        '-x', '--exclude',
        nargs='*',
        default=['build', 'venv'],
        help='List of directory names to exclude (default: build venv)'
    )
    return parser.parse_args()

def main():
    args = parse_arguments()
    extensions = tuple(ext if ext.startswith('.') else f'.{ext}' for ext in args.extensions)
    exclude_dirs = set(args.exclude)
    collected_files = collect_files(args.start_dir, extensions, exclude_dirs)
    
    write_output(collected_files, args.output, args.start_dir, exclude_dirs)
    
    if collected_files:
        print(f"Consolidated {len(collected_files)} files into '{args.output}', excluding import statements.")
    else:
        print("No files found with the specified extensions.")
    
    print("A folder structure (ASCII tree) is included at the top of the output file.")

if __name__ == "__main__":
    main()
