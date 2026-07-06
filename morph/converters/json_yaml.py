"""converters/json_yaml.py — json <-> yaml, native implementation."""

from __future__ import annotations

import json
from pathlib import Path

import yaml

from ..registry import ConversionResult, register


@register("json", "yaml", backend="native", family="data", description="json → yaml")
def json_to_yaml(input_path: Path, output_path: Path, **options) -> ConversionResult:
    data = json.loads(input_path.read_text(encoding="utf-8"))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(yaml.dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")
    return ConversionResult(output=output_path)


@register("yaml", "json", backend="native", family="data", description="yaml → json")
def yaml_to_json(input_path: Path, output_path: Path, **options) -> ConversionResult:
    data = yaml.safe_load(input_path.read_text(encoding="utf-8"))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return ConversionResult(output=output_path)
