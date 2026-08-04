# -*- coding:utf-8 -*-
from pathlib import Path
from typing import Any, Callable

from fastapi import Request
from fastapi.templating import Jinja2Templates


TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATE_DIR))


def render_dashboard(
    request: Request,
    *,
    version: str,
    database: str,
    query_all: Callable[..., Any],
    query_friend: Callable[..., Any],
) -> Any:
    """Render a readable status dashboard for browsers."""
    stats: dict[str, Any] = {}
    articles: list[dict[str, Any]] = []
    friends: list[dict[str, Any]] = []

    try:
        all_result = query_all(
            ["title", "created", "updated", "link", "author", "avatar"],
            0,
            30,
            "updated",
        )
        if isinstance(all_result, dict) and "statistical_data" in all_result:
            stats = all_result.get("statistical_data", {}) or {}
            articles = all_result.get("article_data", []) or []
    except Exception:
        pass

    try:
        friend_result = query_friend()
        if isinstance(friend_result, list):
            friends = friend_result
    except Exception:
        pass

    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "request": request,
            "version": version,
            "database": database,
            "last_updated": stats.get("last_updated_time", "暂无更新记录"),
            "friends_num": stats.get("friends_num", 0),
            "active_num": stats.get("active_num", 0),
            "error_num": stats.get("error_num", 0),
            "article_num": stats.get("article_num", 0),
            "articles": articles,
            "friends": friends,
        },
    )
