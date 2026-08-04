import os
import tempfile
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from db import models


@pytest.fixture(scope="session", autouse=True)
def isolated_database():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    os.environ["TEST_DB_PATH"] = path
    db_path = Path(path).as_posix()
    engine = create_engine(f"sqlite:///{db_path}")
    models.Model.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    for index in range(1, 31):
        session.add(
            models.Post(
                title=f"测试文章{index}",
                created="2026-08-01",
                updated="2026-08-01",
                link=f"https://example.com/post/{index}",
                author="测试",
                avatar="",
                rule="updated",
                createdAt="2026-08-01 00:00:00",
            )
        )
    session.add(
        models.Friend(
            name="失联测试",
            link="https://example.com",
            avatar="",
            error=True,
            lost=True,
            errorSince="2026-08-01 00:00:00",
            lostSince="2026-08-01 00:00:00",
            createdAt="2026-08-01 00:00:00",
        )
    )
    session.commit()
    session.close()
    engine.dispose()
    yield
    try:
        Path(path).unlink()
    except OSError:
        pass
