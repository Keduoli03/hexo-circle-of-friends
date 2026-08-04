from fastapi.testclient import TestClient

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
