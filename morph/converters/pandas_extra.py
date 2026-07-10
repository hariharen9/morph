"""
converters/pandas_extra.py — additional data formats supported natively by pandas.
"""
from __future__ import annotations

from pathlib import Path
import pandas as pd
from sqlalchemy import create_engine, inspect

from ..registry import ConversionResult, register, OptionSpec

def _read_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, keep_default_na=True)

# ── Parquet ───────────────────────────────────────────────────────────────────
@register("csv", "parquet", backend="native", family="data", description="csv → parquet")
def csv_to_parquet(input_path: Path, output_path: Path, **options) -> ConversionResult:
    df = _read_csv(input_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(output_path, index=False)
    return ConversionResult(output=output_path, rows=len(df))

@register("parquet", "csv", backend="native", family="data", description="parquet → csv")
def parquet_to_csv(input_path: Path, output_path: Path, **options) -> ConversionResult:
    df = pd.read_parquet(input_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False)
    return ConversionResult(output=output_path, rows=len(df))

# ── Feather ───────────────────────────────────────────────────────────────────
@register("csv", "feather", backend="native", family="data", description="csv → feather")
def csv_to_feather(input_path: Path, output_path: Path, **options) -> ConversionResult:
    df = _read_csv(input_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_feather(output_path)
    return ConversionResult(output=output_path, rows=len(df))

@register("feather", "csv", backend="native", family="data", description="feather → csv")
def feather_to_csv(input_path: Path, output_path: Path, **options) -> ConversionResult:
    df = pd.read_feather(input_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False)
    return ConversionResult(output=output_path, rows=len(df))

# ── ODS ───────────────────────────────────────────────────────────────────────
@register("csv", "ods", backend="native", family="data", description="csv → ods")
def csv_to_ods(input_path: Path, output_path: Path, **options) -> ConversionResult:
    df = _read_csv(input_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_excel(output_path, index=False, engine="odf")
    return ConversionResult(output=output_path, rows=len(df))

@register("ods", "csv", backend="native", family="data", description="ods → csv")
def ods_to_csv(input_path: Path, output_path: Path, **options) -> ConversionResult:
    df = pd.read_excel(input_path, engine="odf")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False)
    return ConversionResult(output=output_path, rows=len(df))

# ── XML ───────────────────────────────────────────────────────────────────────
@register("csv", "xml", backend="native", family="data", description="csv → xml")
def csv_to_xml(input_path: Path, output_path: Path, **options) -> ConversionResult:
    df = _read_csv(input_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_xml(output_path, index=False)
    return ConversionResult(output=output_path, rows=len(df))

@register("xml", "csv", backend="native", family="data", description="xml → csv")
def xml_to_csv(input_path: Path, output_path: Path, **options) -> ConversionResult:
    df = pd.read_xml(input_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False)
    return ConversionResult(output=output_path, rows=len(df))

# ── HTML ──────────────────────────────────────────────────────────────────────
@register("csv", "html", backend="native", family="data", description="csv → html (table)")
def csv_to_html(input_path: Path, output_path: Path, **options) -> ConversionResult:
    df = _read_csv(input_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_html(output_path, index=False)
    return ConversionResult(output=output_path, rows=len(df))

@register("html", "csv", backend="native", family="data", description="html (first table) → csv")
def html_to_csv(input_path: Path, output_path: Path, **options) -> ConversionResult:
    dfs = pd.read_html(input_path)
    if not dfs:
        raise ValueError("No tables found in HTML")
    df = dfs[0]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False)
    return ConversionResult(output=output_path, rows=len(df))

# ── SQLite ────────────────────────────────────────────────────────────────────
_SQLITE_IN_OPTIONS = [
    OptionSpec("table", ("--table",), "Table name to read from SQLite. Defaults to the first table found."),
]

@register("sqlite", "csv", backend="native", family="data", description="sqlite → csv", options=_SQLITE_IN_OPTIONS)
def sqlite_to_csv(input_path: Path, output_path: Path, *, table: str | None = None, **options) -> ConversionResult:
    engine = create_engine(f"sqlite:///{input_path.absolute()}")
    
    if not table:
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        if not tables:
            raise ValueError(f"No tables found in {input_path}")
        table = tables[0]
        
    df = pd.read_sql_table(table, engine)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False)
    return ConversionResult(output=output_path, rows=len(df))

_SQLITE_OUT_OPTIONS = [
    OptionSpec("table", ("--table",), "Table name to write to SQLite. Defaults to the file stem."),
]

@register("csv", "sqlite", backend="native", family="data", description="csv → sqlite", options=_SQLITE_OUT_OPTIONS)
def csv_to_sqlite(input_path: Path, output_path: Path, *, table: str | None = None, **options) -> ConversionResult:
    df = _read_csv(input_path)
    if not table:
        table = input_path.stem
    
    output_path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(f"sqlite:///{output_path.absolute()}")
    df.to_sql(table, engine, index=False, if_exists="replace")
    return ConversionResult(output=output_path, rows=len(df))
