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
            # Remove comments and empty lines in the .gitignore itself
            patterns = [p for p in lines if p.strip() and not p.strip().startswith('#')]
            # The .gitignore file's parent directory, relative to start_dir
            base_dir = gitignore.parent
            try:
                relative_base = str(base_dir.relative_to(start_dir)).replace('\\', '/')
            except ValueError:
                # If base_dir is not relative to start_dir, skip this gitignore
                print(f"Warning: .gitignore at {gitignore} is not under the start_dir {start_dir}. Skipping.")
                continue
            new_patterns = []
            for p in patterns:
                # If the pattern starts with '/', in .gitignore terms this means
                # "relative to .gitignore's folder"—so we prepend the subfolder path.
                if p.startswith('/'):
                    stripped = p.lstrip('/')
                    if relative_base in ("", "."):
                        new_patterns.append(stripped)
                    else:
                        new_patterns.append(f"{relative_base}/{stripped}")
                else:
                    # Ensure there's no leading '/' to prevent absolute matching
                    p = p.lstrip('/')
                    if relative_base in ("", "."):
                        new_patterns.append(p)
                    else:
                        new_patterns.append(f"{relative_base}/{p}")
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

# ----------------------------------------------------------------------------
# 1. Helper: Identify import lines
# ----------------------------------------------------------------------------
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
        '.svelte': re.compile(r'<script[^>]*>\s*import\s+.*\s+from\s+.*;\s*</script>')
        # Add more patterns if needed
    }
    pattern = import_patterns.get(file_extension, None)
    if pattern:
        return bool(pattern.match(line))
    return False

# ----------------------------------------------------------------------------
# 2. Helper: Remove comments (supports multi-line comments)
# ----------------------------------------------------------------------------
def remove_comments(lines, file_extension):
    """
    Removes all comments from the list of lines. Handles single-line and multi-line comments.
    Returns a new list of lines without comments.
    """
    in_multiline_comment = False
    uncommented_lines = []
    for line in lines:
        original_line = line
        if in_multiline_comment:
            end_comment = line.find('*/')
            if end_comment != -1:
                in_multiline_comment = False
                line = line[end_comment + 2:]
                # Continue processing the rest of the line after '*/'
            else:
                # Entire line is within a multi-line comment
                continue
        while True:
            start_comment = line.find('/*')
            start_doc_comment = line.find('/**')
            single_line_comment = line.find('//')
            hash_comment = line.find('#')
            html_comment = line.find('<!--')
            sql_single_dash = line.find('--')

            # Determine the earliest comment start
            candidates = []
            if start_comment != -1:
                candidates.append(('/*', start_comment))
            if start_doc_comment != -1:
                candidates.append(('/**', start_doc_comment))
            if single_line_comment != -1:
                candidates.append(('//', single_line_comment))
            if hash_comment != -1:
                candidates.append(('#', hash_comment))
            if html_comment != -1:
                candidates.append(('<!--', html_comment))
            if sql_single_dash != -1:
                candidates.append(('--', sql_single_dash))

            if not candidates:
                break  # No comments in the line

            # Find the first occurring comment
            comment_type, comment_start = min(candidates, key=lambda x: x[1])

            if comment_type in ('/*', '/**'):
                end_comment = line.find('*/', comment_start + 2)
                if end_comment != -1:
                    # Remove the comment and continue processing
                    line = line[:comment_start] + line[end_comment + 2:]
                else:
                    # Start of multi-line comment with no end on this line
                    in_multiline_comment = True
                    line = line[:comment_start]
                    break  # Exit the while loop
            elif comment_type in ('//', '#', '--'):
                # Remove the comment from here to the end of the line
                line = line[:comment_start]
                break  # Exit the while loop
            elif comment_type == '<!--':
                end_comment = line.find('-->', comment_start + 4)
                if end_comment != -1:
                    # Remove the HTML comment and continue processing
                    line = line[:comment_start] + line[end_comment + 3:]
                else:
                    # Start of HTML comment with no end on this line
                    in_multiline_comment = True
                    line = line[:comment_start]
                    break  # Exit the while loop

        # After removing comments, check if the line is not empty
        if line.strip() != '':
            uncommented_lines.append(line)
    return uncommented_lines

# ----------------------------------------------------------------------------
# 3. Helper: Should we remove the entire line (e.g., lines that begin with package)?
# ----------------------------------------------------------------------------
def should_remove_entire_line(line, file_extension):
    """ 
    Returns True if the line should be removed entirely (e.g., 'package' lines in .java/.kt).
    """
    # We remove lines beginning with 'package' in Kotlin and Java
    if file_extension in ('.kt', '.kts', '.java'):
        if re.match(r'^\s*package\s', line):
            return True
    return False

def write_output(collected_files, output_file, file_extension_set=set()):
    with open(output_file, 'w', encoding='utf-8') as outfile:
        if collected_files:
            for file_path in collected_files:
                outfile.write(f"\n\n{file_path}\n\n")
                try:
                    with file_path.open('r', encoding='utf-8') as infile:
                        lines = infile.readlines()
                    # Remove comments
                    uncommented = remove_comments(lines, file_path.suffix)
                    for line in uncommented:
                        # 1) Remove import lines
                        if is_import_line(line, file_path.suffix):
                            continue
                        # 2) Check if the entire line should be removed (e.g., 'package')
                        if should_remove_entire_line(line, file_path.suffix):
                            continue
                        # 3) Write the processed line
                        outfile.write(line)
                except Exception as e:
                    outfile.write(f"<!-- Could not read file: {e} -->\n")
        else:
            outfile.write("\n\n[No files found with the specified extensions.]\n")

def parse_arguments():
    parser = argparse.ArgumentParser(
        description="Traverse directories, generate a tree of the structure, and consolidate code files, "
                    "excluding import statements, gitignored paths, all comments, and certain lines."
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
            '.kt',    # Kotlin
            '.kts',   # Kotlin script
            '.java',  # Java
            '.svelte',# Svelte
            '.js',    # JavaScript
            '.ts',    # TypeScript
            '.html',  # HTML
            '.css',   # CSS
            '.py',    # Python
            '.sq',    # SqlDelight
            '.sqm'    # SqlDelight Migration
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
        print(f"Consolidated {len(collected_files)} files into '{args.output}', excluding import statements, comments, and certain lines.")
    else:
        print("No files found with the specified extensions.")

if __name__ == "__main__":
    main()
