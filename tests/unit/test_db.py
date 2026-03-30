import backend.app.db as db_module


def test_session_factory_is_initialized_lazily(monkeypatch):
    created_engines: list[tuple[str, dict]] = []

    monkeypatch.setattr(db_module, "engine", None)
    monkeypatch.setattr(db_module, "_session_factory", None)

    def fake_create_engine(url, **kwargs):
        created_engines.append((url, kwargs))
        return object()

    def fake_sessionmaker(**kwargs):
        return lambda: ("session", kwargs["bind"])

    monkeypatch.setattr(db_module, "create_engine", fake_create_engine)
    monkeypatch.setattr(db_module, "sessionmaker", fake_sessionmaker)

    assert created_engines == []

    session_factory = db_module.get_session_factory()
    session = session_factory()

    assert session[0] == "session"
    assert len(created_engines) == 1
