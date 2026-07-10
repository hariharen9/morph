"""
registry.py — the heart of morph's "anything to anything" engine.

Every converter (native Python or a wrapper around an external binary like
pandoc/ffmpeg) registers itself as a directed edge: src format -> dst format.
morph then does a breadth-first search over that graph so that even formats
with no *direct* converter can still be reached via a chain
(e.g. odt -> docx -> pdf), as long as every edge on the path is registered.

Nothing in here knows about pandoc, ffmpeg, or pandas specifically — that
knowledge lives in morph/converters/*.py, which import `register` from here
and populate the graph at import time.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional


@dataclass
class ConversionResult:
    """What every converter function returns."""
    output: Path
    rows: Optional[int] = None      # for tabular data
    pages: Optional[int] = None     # for documents
    duration: Optional[float] = None  # seconds, for audio/video
    extra: dict = field(default_factory=dict)


@dataclass(frozen=True)
class OptionSpec:
    """One CLI flag a converter accepts, e.g. --table-style or --no-header.

    `name` must match the keyword argument the converter function expects.
    `action` mirrors argparse: "store_true"/"store_false" for flags, None for
    a value-taking option (parsed as `type`).
    """
    name: str
    flags: tuple[str, ...]
    help: str = ""
    default: object = None
    type: type = str
    action: Optional[str] = None


@dataclass(frozen=True)
class ConverterSpec:
    src: str
    dst: str
    func: Callable[..., ConversionResult]
    backend: str                       # "native" | "pandoc" | "ffmpeg" | ...
    requires_binary: Optional[str] = None
    family: str = "data"               # data | document | image | audio | video | archive | font | ebook
    description: str = ""
    lossy: bool = False                # flag conversions that can't round-trip cleanly
    options: tuple[OptionSpec, ...] = field(default_factory=tuple)
    supports_progress: bool = False    # True if func accepts a `_progress(frac, status)` kwarg

    @property
    def key(self) -> tuple[str, str]:
        return (self.src, self.dst)


class Registry:
    def __init__(self) -> None:
        self._edges: dict[tuple[str, str], ConverterSpec] = {}

    def register(
        self,
        src: str,
        dst: str,
        *,
        backend: str,
        requires_binary: Optional[str] = None,
        family: str = "data",
        description: str = "",
        lossy: bool = False,
        options: Optional[list[OptionSpec]] = None,
        supports_progress: bool = False,
    ):
        """Decorator: register `func` as a converter for src -> dst."""
        def deco(func: Callable[..., ConversionResult]):
            spec = ConverterSpec(
                src=_norm(src), dst=_norm(dst), func=func, backend=backend,
                requires_binary=requires_binary, family=family,
                description=description, lossy=lossy,
                options=tuple(options or ()), supports_progress=supports_progress,
            )
            self._edges[spec.key] = spec
            return func
        return deco

    def all_formats(self) -> set[str]:
        fmts: set[str] = set()
        for s, d in self._edges:
            fmts.add(s)
            fmts.add(d)
        return fmts

    def direct(self, src: str, dst: str) -> Optional[ConverterSpec]:
        return self._edges.get((_norm(src), _norm(dst)))

    def find_path(self, src: str, dst: str) -> Optional[list[ConverterSpec]]:
        """BFS shortest conversion path (fewest hops) from src to dst."""
        src, dst = _norm(src), _norm(dst)
        if src == dst:
            return []

        graph: dict[str, list[ConverterSpec]] = {}
        for spec in self._edges.values():
            graph.setdefault(spec.src, []).append(spec)

        visited = {src}
        queue: deque[tuple[str, list[ConverterSpec]]] = deque([(src, [])])
        while queue:
            node, path = queue.popleft()
            for spec in graph.get(node, []):
                if spec.dst == dst:
                    return path + [spec]
                if spec.dst not in visited:
                    visited.add(spec.dst)
                    queue.append((spec.dst, path + [spec]))
        return None

    def reachable_targets(self, src: str) -> dict[str, list[ConverterSpec]]:
        """Every format reachable from src, mapped to the path that gets there."""
        src = _norm(src)
        graph: dict[str, list[ConverterSpec]] = {}
        for spec in self._edges.values():
            graph.setdefault(spec.src, []).append(spec)

        results: dict[str, list[ConverterSpec]] = {}
        visited = {src}
        queue: deque[tuple[str, list[ConverterSpec]]] = deque([(src, [])])
        while queue:
            node, path = queue.popleft()
            for spec in graph.get(node, []):
                if spec.dst not in visited:
                    visited.add(spec.dst)
                    new_path = path + [spec]
                    results[spec.dst] = new_path
                    queue.append((spec.dst, new_path))
        return results

    def combined_options(self, path: list[ConverterSpec]) -> list[OptionSpec]:
        """All options across every hop in a path, flattened for the CLI parser."""
        combined: list[OptionSpec] = []
        seen_flags: set[str] = set()
        for spec in path:
            for opt in spec.options:
                colliding = seen_flags & set(opt.flags)
                if colliding:
                    # two hops in the same chain want the same flag name — extremely
                    # unlikely given today's converters, but fail loudly rather than
                    # silently letting one shadow the other.
                    raise ValueError(
                        f"Flag collision on {colliding} between hops in this conversion path"
                    )
                seen_flags.update(opt.flags)
                combined.append(opt)
        return combined

    def all_options(self) -> dict[str, list[OptionSpec]]:
        """All options across the entire registry, grouped by family."""
        families: dict[str, list[OptionSpec]] = {}
        seen_names: set[str] = set()
        
        for spec in self._edges.values():
            for opt in spec.options:
                if opt.name not in seen_names:
                    seen_names.add(opt.name)
                    families.setdefault(spec.family, []).append(opt)
                    
        return families

    def known_binaries(self) -> set[str]:
        return {spec.requires_binary for spec in self._edges.values() if spec.requires_binary}

    def required_binaries(self, path: list[ConverterSpec]) -> list[str]:
        seen: list[str] = []
        for spec in path:
            if spec.requires_binary and spec.requires_binary not in seen:
                seen.append(spec.requires_binary)
        return seen

    def formats_by_family(self) -> dict[str, set[str]]:
        """All formats grouped by their converter family."""
        families: dict[str, set[str]] = {}
        for spec in self._edges.values():
            families.setdefault(spec.family, set()).add(spec.src)
            families.setdefault(spec.family, set()).add(spec.dst)
        return families

    def edges_by_family(self) -> dict[str, list[ConverterSpec]]:
        """All direct edges grouped by family."""
        families: dict[str, list[ConverterSpec]] = {}
        for spec in self._edges.values():
            families.setdefault(spec.family, []).append(spec)
        return families

    def family_backends(self) -> dict[str, set[str]]:
        """Primary backends used by each family."""
        result: dict[str, set[str]] = {}
        for spec in self._edges.values():
            result.setdefault(spec.family, set()).add(spec.backend)
        return result


def _norm(fmt: str) -> str:
    return fmt.lower().lstrip(".")


# extensions where the true format spans more than one suffix
_COMPOUND_EXTENSIONS = {
    ".tar.gz": "tar.gz", ".tgz": "tar.gz",
    ".tar.bz2": "tar.bz2", ".tbz2": "tar.bz2",
    ".tar.xz": "tar.xz", ".txz": "tar.xz",
}


def detect_format(path: Path) -> str:
    """Format id for a file path, correctly handling compound extensions
    like .tar.gz (where Path.suffix alone would only see '.gz')."""
    name = path.name.lower()
    for ext, fmt in _COMPOUND_EXTENSIONS.items():
        if name.endswith(ext):
            return fmt
    return _norm(path.suffix)


# Single shared instance every converter module registers against.
registry = Registry()
register = registry.register
