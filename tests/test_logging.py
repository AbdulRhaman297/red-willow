import main


def test_log_file_written(tmp_path, monkeypatch):
    # create a temp log file path
    log_file = tmp_path / "test.log"
    monkeypatch.setenv("LOG_FILE", str(log_file))
    monkeypatch.setenv("OPENWEATHER_API_KEY", "FAKE")
    # reload main so logging picks up env var
    import importlib

    importlib.reload(main)

    # run a command (no audio) which should cause a log entry
    main.run_single_command("weather in Testville", no_audio=True)

    # ensure handlers flushed
    for h in main.logger.handlers:
        try:
            h.flush()
        except Exception:
            pass

    assert log_file.exists(), "Log file was not created"
    content = log_file.read_text()
    assert (
        ("Processing command" in content)
        or ("Weather in" in content)
        or ("weather in" in content.lower())
    )
