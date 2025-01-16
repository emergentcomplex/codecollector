#!/usr/bin/env python3

import os
import argparse
from pathlib import Path
import re
import pathspec

def collect_gitignore_patterns(start_dir):
    """
    Collects all .gitignore patterns from the directory tree starting at start_dir.
    Returns a PathSpec object containing all the compiled patterns.
    """
    gitignore_files = list(Path(start_dir).rglob('.gitignore'))
    all_patterns = []
    for gitignore in gitignore_files:
        try:
            with gitignore.open('r', encoding='utf-8') as f:
                lines = f.read().splitlines()
                # Remove comments and empty lines
                patterns = [p for p in lines if p.strip() and not p.strip().startswith('#')]
                
                # The .gitignore file's parent directory, relative to start_dir
                base_dir = gitignore.parent
                relative_base = str(base_dir.relative_to(start_dir)).replace('\\', '/')
                
                new_patterns = []
                for p in patterns:
                    # If the pattern starts with '/', in .gitignore terms this means
                    # "relative to .gitignore's folder"—so we prepend the subfolder path.
                    if p.startswith('/'):
                        new_patterns.append(relative_base + p)
                    else:
                        new_patterns.append(relative_base + '/' + p)
                
                all_patterns.extend(new_patterns)
        except Exception as e:
            print(f"Warning: Could not read {gitignore}: {e}")
    return pathspec.PathSpec.from_lines('gitwildmatch', all_patterns)

def collect_files(start_dir, extensions, exclude_dirs, ignore_spec):
    """
    Collect files recursively from start_dir if they match the given extensions,
    excluding specified directories and gitignored paths.
    """
    collected = []
    start_dir = Path(start_dir).resolve()
    for root, dirs, files in os.walk(start_dir):
        current_dir = Path(root).relative_to(start_dir)
        
        # Prepare the list of dirs to remove in-place
        dirs_to_remove = []
        for d in dirs:
            dir_path = (current_dir / d).as_posix()
            if ignore_spec.match_file(dir_path + '/'):
                dirs_to_remove.append(d)
        
        # Exclude directories based on .gitignore and predefined exclude_dirs
        dirs[:] = [d for d in dirs if d not in exclude_dirs and d not in dirs_to_remove]
        
        for file in files:
            file_path = (current_dir / file).as_posix()
            # Check if the file is ignored
            if ignore_spec.match_file(file_path):
                continue
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

def write_output(collected_files, output_file):
    with open(output_file, 'w', encoding='utf-8') as outfile:
        if collected_files:
            outfile.write("\n\nConsolidated Code Files (Import statements excluded):\n")
            for file_path in collected_files:
                outfile.write(f"\n\n# File: {file_path}\n\n")
                try:
                    with file_path.open('r', encoding='utf-8') as infile:
                        for line in infile:
                            if not is_import_line(line, file_path.suffix):
                                outfile.write(line)
                except Exception as e:
                    outfile.write(f"<!-- Could not read file: {e} -->\n")
        else:
            outfile.write("\n\n[No files found with the specified extensions.]\n")

def parse_arguments():
    parser = argparse.ArgumentParser(
        description="Traverse directories, generate a tree of the structure, and consolidate code files, excluding import statements and gitignored paths."
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
            '.css',     # CSS
            '.py',      # Python
            '.sq',      # SqlDelight
            '.sqm'      # SqlDelight Migration
        ],
        help=(
            "List of file extensions to include (default: "
            ".kt .kts .java .svelte .js .ts .html .css .py .sq .sqm)"
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

    # Collect all .gitignore patterns
    ignore_spec = collect_gitignore_patterns(args.start_dir)

    # Collect the files to be consolidated
    collected_files = collect_files(args.start_dir, extensions, exclude_dirs, ignore_spec)
    
    # Write the consolidated output
    write_output(collected_files, args.output)
    
    if collected_files:
        print(f"Consolidated {len(collected_files)} files into '{args.output}', excluding import statements and gitignored paths.")
    else:
        print("No files found with the specified extensions.")

if __name__ == "__main__":
    main()
