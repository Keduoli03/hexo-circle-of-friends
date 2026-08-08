from fastapi.testclient import TestClient

from api.article_reader import ArticleFetchError
from api.index import app


client = TestClient(app)


def test_root_returns_dashboard_for_browser():
    response = client.get("/", headers={"Accept": "text/html"})
    assert response.status_code == 200
    assert "友链朋友圈" in response.text
    assert 'class="topnav"' in response.text
    assert 'id="articles"' in response.text
    assert "加载更多文章" in response.text
    assert "接口调试台" in response.text
    assert "已失联" in response.text
    assert response.text.count('class="article-row"') > 12
    assert '/read?link=' in response.text
    assert "原文 ↗" in response.text


def test_dashboard_sorts_normal_then_error_then_lost(monkeypatch):
    monkeypatch.setattr(
        "api.index.query_friend",
        lambda: [
            {
                "name": "失联友链",
                "link": "https://lost.example.com",
                "avatar": "",
                "error": True,
                "lost": True,
            },
            {
                "name": "正常友链一",
                "link": "https://normal-1.example.com",
                "avatar": "",
                "error": False,
                "lost": False,
            },
            {
                "name": "异常友链",
                "link": "https://error.example.com",
                "avatar": "",
                "error": True,
                "lost": False,
            },
            {
                "name": "正常友链二",
                "link": "https://normal-2.example.com",
                "avatar": "",
                "error": False,
                "lost": False,
            },
        ],
    )

    response = client.get("/", headers={"Accept": "text/html"})

    assert response.status_code == 200
    names = ["正常友链一", "正常友链二", "异常友链", "失联友链"]
    positions = [response.text.index(name) for name in names]
    assert positions == sorted(positions)


def test_root_keeps_json_for_api_clients():
    response = client.get("/")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
    assert response.json()["message"] == "服务运行正常"


def test_all_interface_still_returns_json():
    response = client.get("/all")
    assert response.status_code == 200
    data = response.json()
    assert "statistical_data" in data
    assert "article_data" in data


def test_friend_response_includes_lost_status():
    response = client.get("/friend")
    assert response.status_code == 200
    friend = next(item for item in response.json() if item["name"] == "失联测试")
    assert friend["lost"] is True
    assert friend["lostSince"] == "2026-08-01 00:00:00"


def test_reader_renders_extracted_content(monkeypatch):
    monkeypatch.setattr(
        "api.index.query_article",
        lambda link: {
            "title": "站内阅读测试",
            "link": link,
            "author": "测试作者",
            "created": "2026-08-08",
            "updated": "2026-08-08",
        },
    )
    monkeypatch.setattr(
        "api.index.fetch_article",
        lambda link: {
            "source_url": link,
            "blocks": [
                {
                    "type": "heading",
                    "level": 2,
                    "text": "正文标题",
                    "anchor": "section-1",
                },
                {"type": "paragraph", "text": "这是抓取后的正文。"},
            ],
            "toc": [
                {
                    "anchor": "section-1",
                    "text": "正文标题",
                    "level": 2,
                }
            ],
            "tags": ["测试标签", "站内阅读"],
        },
    )

    response = client.get(
        "/read",
        params={"link": "https://example.com/post"},
        headers={"Accept": "text/html"},
    )
    assert response.status_code == 200
    assert "站内阅读测试" in response.text
    assert "这是抓取后的正文。" in response.text
    assert "打开原文" in response.text
    assert "Contents / 目录" in response.text
    assert "# 测试标签" in response.text
    assert "原文地址" in response.text


def test_reader_rejects_unknown_article(monkeypatch):
    monkeypatch.setattr("api.index.query_article", lambda link: None)
    response = client.get("/read", params={"link": "https://example.com/missing"})
    assert response.status_code == 404


def test_reader_keeps_original_link_when_extraction_fails(monkeypatch):
    link = "https://example.com/post"
    monkeypatch.setattr(
        "api.index.query_article",
        lambda value: {
            "title": "抓取失败测试",
            "link": value,
            "author": "测试作者",
            "created": "2026-08-08",
            "updated": "2026-08-08",
        },
    )
    monkeypatch.setattr(
        "api.index.fetch_article",
        lambda value: (_ for _ in ()).throw(ArticleFetchError("原站拒绝访问")),
    )
    response = client.get("/read", params={"link": link})
    assert response.status_code == 200
    assert "这次没能抓到全文" in response.text
    assert "原站拒绝访问" in response.text
    assert link in response.text
