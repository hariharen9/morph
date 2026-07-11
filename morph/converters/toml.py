"""converters/toml.py — toml <-> json/yaml, via tomlkit.

tomlkit is used for both read and write because it preserves comments and
key ordering on round-trips. For pure data exchange (no comments needed)
the output is still valid TOML.

BFS routing gives toml <-> csv/parquet/etc. for free via json/yaml hops.
"""

from __future__ import annotations

import json
from pathlib import Path

from ..registry import ConversionResult, register


def _require_tomlkit():
    try:
        import tomlkit
        return tomlkit
    except ImportError:
        raise RuntimeError(
            "tomlkit is required for TOML conversion.\n"
            "Install it with: pip install tomlkit"
        )


@register("toml", "json", backend="tomlkit", family="data",
          description="toml -> json")
def toml_to_json(input_path: Path, output_path: Path, **_options) -> ConversionResult:
    tomlkit = _require_tomlkit()
    data = tomlkit.loads(input_path.read_text(encoding="utf-8"))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return ConversionResult(output=output_path)


@register("json", "toml", backend="tomlkit", family="data",
          description="json -> toml")
def json_to_toml(input_path: Path, output_path: Path, **_options) -> ConversionResult:
    tomlkit = _require_tomlkit()
    data = json.loads(input_path.read_text(encoding="utf-8"))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(tomlkit.dumps(data), encoding="utf-8")
    return ConversionResult(output=output_path)


@register("toml", "yaml", backend="tomlkit", family="data",
          description="toml -> yaml")
def toml_to_yaml(input_path: Path, output_path: Path, **_options) -> ConversionResult:
    import yaml
    tomlkit = _require_tomlkit()
    data = tomlkit.loads(input_path.read_text(encoding="utf-8"))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        yaml.dump(dict(data), sort_keys=False, allow_unicode=True), encoding="utf-8"
    )
    return ConversionResult(output=output_path)


@register("yaml", "toml", backend="tomlkit", family="data",
          description="yaml -> toml")
def yaml_to_toml(input_path: Path, output_path: Path, **_options) -> ConversionResult:
    import yaml
    tomlkit = _require_tomlkit()
    data = yaml.safe_load(input_path.read_text(encoding="utf-8"))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(tomlkit.dumps(data), encoding="utf-8")
    return ConversionResult(output=output_path)
