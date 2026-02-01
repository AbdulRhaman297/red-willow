import main


def test_enable_debug_sets_level():
    main.set_log_level("DEBUG")
    assert main.logger.level == main.logging.DEBUG


def test_set_log_file_writes(tmp_path, monkeypatch):
    log_file = tmp_path / "cli_test.log"
    # set via function
    main.set_log_file(str(log_file))
    # run a command to generate logs
    main.run_single_command("weather in Testville", no_audio=True)
    for h in main.logger.handlers:
        try:
            h.flush()
        except Exception:
            pass
    assert log_file.exists()
    content = log_file.read_text()
    assert "Processing command" in content.lower() or "weather" in content.lower()
