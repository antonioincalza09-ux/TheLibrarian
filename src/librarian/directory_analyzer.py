from __future__ import annotations

from collections import Counter
from pathlib import Path

from src.librarian.classifiers import classify_directory, path_tokens
from src.librarian.rules.schema import DirectoryAnalysis, WorkspaceNode


def analyze_directory(
    directory_path: Path,
    root: Path,
    file_nodes: list[WorkspaceNode],
    child_directories: list[Path],
) -> DirectoryAnalysis:
    direct_files = [node for node in file_nodes if Path(node.current_path).parent == directory_path]
    descendant_files = [node for node in file_nodes if _is_descendant(Path(node.current_path), directory_path)]
    extension_counts = Counter(node.extension or "" for node in descendant_files if node.extension)
    language_counts = Counter(node.detected_language or "" for node in descendant_files if node.detected_language)
    token_counts = Counter(token for node in descendant_files for token in path_tokens(Path(node.current_path).name))
    child_names = [path.name for path in child_directories] + [Path(node.current_path).name for node in direct_files]
    analysis = classify_directory(
        directory_path,
        child_names=child_names,
        dominant_languages=[name for name, _ in language_counts.most_common(5)],
        dominant_extensions=[name for name, _ in extension_counts.most_common(5)],
    )
    analysis.direct_file_count = len(direct_files)
    analysis.direct_subdirectory_count = len([path for path in child_directories if path.parent == directory_path])
    analysis.total_file_count = len(descendant_files)
    analysis.recurring_name_tokens = [name for name, _ in token_counts.most_common(8)]
    return analysis


def _is_descendant(path: Path, directory_path: Path) -> bool:
    try:
        path.relative_to(directory_path)
        return True
    except ValueError:
        return False
