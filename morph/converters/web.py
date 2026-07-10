"""
converters/web.py — extract clean documents from URLs.

Powered by `trafilatura`.
"""

from __future__ import annotations

from pathlib import Path

import trafilatura

from ..registry import ConversionResult, register


def _fetch_static(url: str, output_format: str) -> str:
    downloaded = trafilatura.fetch_url(url)
    if not downloaded:
        raise RuntimeError(f"Failed to fetch {url}")
        
    if output_format == "html_raw":
        return downloaded
        
    result = trafilatura.extract(downloaded, output_format=output_format)
    if not result:
        raise RuntimeError(f"Failed to extract content from {url} (it might be empty or a captcha)")
    return result


def _fetch_dynamic(url: str, output_format: str) -> str:
    import asyncio
    
    try:
        from crawl4ai import AsyncWebCrawler
    except ImportError:
        raise RuntimeError("crawl4ai is required for --js, but it's not installed.")
        
    async def run():
        async with AsyncWebCrawler() as crawler:
            return await crawler.arun(url)
            
    result = asyncio.run(run())
    if not result.success:
        raise RuntimeError(f"Failed to crawl {url} with JS: {result.error_message}")
        
    if output_format == "markdown":
        return result.markdown
    if output_format == "html_raw":
        return result.html
        
    # for txt and xml, fallback to trafilatura but feed it the JS-rendered HTML
    content = trafilatura.extract(result.html, output_format=output_format)
    if not content:
        raise RuntimeError(f"Failed to extract {output_format} from JS-rendered content.")
    return content


@register("url", "md", backend="trafilatura", family="web", description="url → md (clean article)")
def url_to_md(input_path: str | Path, output_path: Path, **options) -> ConversionResult:
    url = str(input_path)
    content = _fetch_dynamic(url, "markdown") if options.get("js") else _fetch_static(url, "markdown")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content, encoding="utf-8")
    return ConversionResult(output=output_path)


@register("url", "txt", backend="trafilatura", family="web", description="url → txt (clean article)")
def url_to_txt(input_path: str | Path, output_path: Path, **options) -> ConversionResult:
    url = str(input_path)
    content = _fetch_dynamic(url, "txt") if options.get("js") else _fetch_static(url, "txt")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content, encoding="utf-8")
    return ConversionResult(output=output_path)


@register("url", "xml", backend="trafilatura", family="web", description="url → xml (clean article tree)")
def url_to_xml(input_path: str | Path, output_path: Path, **options) -> ConversionResult:
    url = str(input_path)
    content = _fetch_dynamic(url, "xml") if options.get("js") else _fetch_static(url, "xml")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content, encoding="utf-8")
    return ConversionResult(output=output_path)


@register("url", "html", backend="trafilatura", family="web", description="url → html (raw dump)")
def url_to_html(input_path: str | Path, output_path: Path, **options) -> ConversionResult:
    url = str(input_path)
    content = _fetch_dynamic(url, "html_raw") if options.get("js") else _fetch_static(url, "html_raw")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content, encoding="utf-8")
    return ConversionResult(output=output_path)

