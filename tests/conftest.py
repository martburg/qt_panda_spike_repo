def pytest_configure(config):
    config.addinivalue_line("markers", "integration: integration-style UDP roundtrip tests")
