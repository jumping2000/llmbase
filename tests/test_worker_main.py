from pathlib import Path


def test_worker_main_runs_worker_on_project_root(monkeypatch):
    from llmwiki import worker_main

    seen = {}

    def fake_run_worker(base_dir):
        seen["base_dir"] = base_dir

    monkeypatch.setattr(worker_main, "load_config", lambda base_dir: {"worker": {"enabled": True}})
    monkeypatch.setattr(worker_main, "run_worker", fake_run_worker)

    worker_main.main()

    assert seen["base_dir"] == Path(worker_main.__file__).resolve().parent.parent


def test_worker_main_waits_when_disabled(monkeypatch):
    from llmwiki import worker_main

    calls = {"sleep": 0, "run_worker": 0}
    states = iter([
        {"worker": {"enabled": False}},
        {"worker": {"enabled": True}},
    ])

    monkeypatch.setattr(worker_main, "load_config", lambda base_dir: next(states))

    def fake_sleep(seconds):
        calls["sleep"] += 1

    def fake_run_worker(base_dir):
        calls["run_worker"] += 1

    monkeypatch.setattr(worker_main.time, "sleep", fake_sleep)
    monkeypatch.setattr(worker_main, "run_worker", fake_run_worker)

    worker_main.main(poll_interval_seconds=0)

    assert calls == {"sleep": 1, "run_worker": 1}