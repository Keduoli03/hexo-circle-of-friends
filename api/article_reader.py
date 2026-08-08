"""Safe, best-effort extraction of readable article content."""

from __future__ import annotations

import ipaddress
import re
import socket
import time
from functools import lru_cache
from urllib.parse import urljoin, urlparse

import requests
from lxml import html


class ArticleFetchError(RuntimeError):
    """A user-facing article fetch failure."""


_SPACE_RE = re.compile(r"[\t\r\n ]+")
_BLOCK_TAGS = {"p", "pre", "blockquote", "li", "h1", "h2", "h3", "h4", "h5", "h6"}
_CONTAINER_TAGS = {"pre", "blockquote", "li"}


def _validate_public_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ArticleFetchError("文章地址不是有效的 HTTP(S) 链接")

    try:
        addresses = {
            item[4][0]
            for item in socket.getaddrinfo(parsed.hostname, parsed.port or 443)
        }
    except OSError as exc:
        raise ArticleFetchError("无法解析文章所在网站") from exc

    if not addresses or any(not ipaddress.ip_address(address).is_global for address in addresses):
        raise ArticleFetchError("文章地址指向了不可访问的网络位置")


def _download(url: str) -> tuple[str, str]:
    current_url = url
    session = requests.Session()
    session.trust_env = False
    headers = {
        "User-Agent": "RSS-Circle-Reader/1.0 (+https://github.com/Keduoli03/rss_circle)",
        "Accept": "text/html,application/xhtml+xml;q=0.9",
    }

    for _ in range(4):
        _validate_public_url(current_url)
        try:
            response = session.get(
                current_url,
                headers=headers,
                timeout=(5, 12),
                allow_redirects=False,
                stream=True,
            )
        except requests.RequestException as exc:
            raise ArticleFetchError("暂时无法连接原文网站") from exc

        if response.is_redirect or response.is_permanent_redirect:
            location = response.headers.get("location")
            response.close()
            if not location:
                raise ArticleFetchError("原文网站返回了无效跳转")
            current_url = urljoin(current_url, location)
            continue

        try:
            response.raise_for_status()
        except requests.RequestException as exc:
            response.close()
            raise ArticleFetchError(f"原文网站返回 HTTP {response.status_code}") from exc

        content_type = response.headers.get("content-type", "").lower()
        if "html" not in content_type and "xhtml" not in content_type:
            response.close()
            raise ArticleFetchError("原文不是可阅读的网页内容")

        body = bytearray()
        for chunk in response.iter_content(64 * 1024):
            body.extend(chunk)
            if len(body) > 3 * 1024 * 1024:
                response.close()
                raise ArticleFetchError("原文页面过大，已停止抓取")

        encoding = response.encoding
        if not encoding or encoding.lower() == "iso-8859-1":
            encoding = response.apparent_encoding or "utf-8"
        response.close()
        return body.decode(encoding, errors="replace"), current_url

    raise ArticleFetchError("原文网站跳转次数过多")


def _plain_text(element, *, preserve_space: bool = False) -> str:
    text = "".join(element.itertext())
    return text.strip() if preserve_space else _SPACE_RE.sub(" ", text).strip()


def _pick_article_root(document):
    selectors = [
        "//article",
        "//main",
        "//*[contains(concat(' ', normalize-space(@class), ' '), ' post-content ')]",
        "//*[contains(concat(' ', normalize-space(@class), ' '), ' article-content ')]",
        "//*[contains(concat(' ', normalize-space(@class), ' '), ' entry-content ')]",
        "//*[@id='post' or @id='article' or @id='content' or @id='main']",
        "//body",
    ]
    for selector in selectors:
        candidates = document.xpath(selector)
        candidates = [node for node in candidates if len(_plain_text(node)) >= 160]
        if candidates:
            return max(candidates, key=lambda node: len(_plain_text(node)))
    return document


def _extract_tags(page_html: str) -> list[str]:
    try:
        document = html.fromstring(page_html)
    except (ValueError, TypeError):
        return []

    values = document.xpath(
        "//meta[translate(@property, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz')='article:tag']/@content"
        " | //meta[translate(@name, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz')='keywords']/@content"
        " | //meta[translate(@name, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz')='news_keywords']/@content"
    )
    tags: list[str] = []
    for value in values:
        for raw_tag in re.split(r"[,，;；|]", value):
            tag = _SPACE_RE.sub(" ", raw_tag).strip().lstrip("#")
            if tag and len(tag) <= 40 and tag not in tags:
                tags.append(tag)
            if len(tags) >= 12:
                return tags
    return tags


def _extract_blocks(page_html: str, final_url: str) -> list[dict[str, str | int]]:
    try:
        document = html.fromstring(page_html, base_url=final_url)
    except (ValueError, TypeError) as exc:
        raise ArticleFetchError("原文网页结构无法解析") from exc

    for node in document.xpath(
        "//script|//style|//noscript|//template|//svg|//canvas|//form|//nav|//footer|//aside"
    ):
        node.drop_tree()

    root = _pick_article_root(document)
    blocks: list[dict[str, str | int]] = []
    seen_images: set[str] = set()
    total_chars = 0
    heading_index = 0

    for element in root.iter():
        tag = element.tag.lower() if isinstance(element.tag, str) else ""
        if tag in _BLOCK_TAGS:
            if any(
                isinstance(parent.tag, str) and parent.tag.lower() in _CONTAINER_TAGS
                for parent in element.iterancestors()
                if parent is not root
            ):
                continue
            text = _plain_text(element, preserve_space=tag == "pre")
            if not text:
                continue
            remaining = 120_000 - total_chars
            if remaining <= 0:
                break
            text = text[:remaining]
            total_chars += len(text)
            if tag.startswith("h"):
                heading_index += 1
                blocks.append(
                    {
                        "type": "heading",
                        "level": int(tag[1]),
                        "text": text,
                        "anchor": f"section-{heading_index}",
                    }
                )
            elif tag == "pre":
                blocks.append({"type": "code", "text": text})
            elif tag == "blockquote":
                blocks.append({"type": "quote", "text": text})
            elif tag == "li":
                blocks.append({"type": "list", "text": text})
            else:
                blocks.append({"type": "paragraph", "text": text})
        elif tag == "img" and len(seen_images) < 40:
            raw_src = element.get("src") or element.get("data-src") or element.get("data-original")
            if not raw_src:
                continue
            src = urljoin(final_url, raw_src.strip())
            if urlparse(src).scheme not in {"http", "https"} or src in seen_images:
                continue
            seen_images.add(src)
            blocks.append(
                {
                    "type": "image",
                    "src": src,
                    "alt": _SPACE_RE.sub(" ", element.get("alt", "")).strip(),
                }
            )

    if not blocks:
        fallback = _plain_text(root)[:120_000]
        if fallback:
            blocks = [{"type": "paragraph", "text": fallback}]
    if not blocks:
        raise ArticleFetchError("没有从页面中识别到正文")
    return blocks


@lru_cache(maxsize=128)
def _fetch_article_cached(url: str, _time_bucket: int) -> dict[str, object]:
    page_html, final_url = _download(url)
    blocks = _extract_blocks(page_html, final_url)
    toc = [
        {
            "anchor": block["anchor"],
            "text": block["text"],
            "level": block["level"],
        }
        for block in blocks
        if block.get("type") == "heading" and int(block.get("level", 2)) >= 2
    ]
    return {
        "source_url": final_url,
        "blocks": blocks,
        "toc": toc,
        "tags": _extract_tags(page_html),
    }


def fetch_article(url: str) -> dict[str, object]:
    """Download and extract one article; successful results are cached for 30 minutes."""
    return _fetch_article_cached(url, int(time.time() // 1800))
