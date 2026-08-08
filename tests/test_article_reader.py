import pytest

from api.article_reader import (
    ArticleFetchError,
    _extract_blocks,
    _extract_tags,
    _validate_public_url,
)


def test_extract_blocks_keeps_readable_structure_and_drops_scripts():
    page = """
    <html><body><article>
      <h1>文章标题</h1>
      <p>第一段正文，包含足够多的文本用于正文识别。</p>
      <p>第二段正文，继续补足内容长度，确保测试选择 article 节点而不是整个页面。</p>
      <blockquote>一段引用内容</blockquote>
      <pre>print(&quot;hello&quot;)</pre>
      <script>alert('bad')</script>
    </article></body></html>
    """
    blocks = _extract_blocks(page, "https://example.com/post")
    text = " ".join(str(block.get("text", "")) for block in blocks)
    assert "文章标题" in text
    assert "第一段正文" in text
    assert "print" in text
    assert "alert" not in text
    assert any(block["type"] == "quote" for block in blocks)
    assert any(block["type"] == "code" for block in blocks)
    assert next(block for block in blocks if block["type"] == "heading")["anchor"] == "section-1"


def test_extract_tags_supports_article_tags_and_keywords():
    page = """
    <html><head>
      <meta property="article:tag" content="Rust">
      <meta name="keywords" content="后端开发, RSS, Rust">
    </head><body></body></html>
    """
    assert _extract_tags(page) == ["Rust", "后端开发", "RSS"]


def test_validate_public_url_rejects_localhost():
    with pytest.raises(ArticleFetchError):
        _validate_public_url("http://127.0.0.1/private")
