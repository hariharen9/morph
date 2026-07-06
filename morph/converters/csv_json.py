"""converters/csv_json.py — csv <-> json, native pandas implementation."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from ..registry import ConversionResult, register


@register("csv", "json", backend="native", family="data", description="csv → json (records)")
def csv_to_json(input_path: Path, output_path: Path, **options) -> ConversionResult:
    df = pd.read_csv(input_path, dtype=str, keep_default_na=True)
    records = json.loads(df.to_json(orient="records", date_format="iso"))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(records, indent=2, ensure_ascii=False), encoding="utf-8")
    return ConversionResult(output=output_path, rows=len(df))


@register("json", "csv", backend="native", family="data", description="json (list of records) → csv", lossy=True)
def json_to_csv(input_path: Path, output_path: Path, **options) -> ConversionResult:
    data = json.loads(input_path.read_text(encoding="utf-8"))
    df = pd.json_normalize(data)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False)
    return ConversionResult(output=output_path, rows=len(df))
