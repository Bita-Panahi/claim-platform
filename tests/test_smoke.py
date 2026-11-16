import importlib


def test_ingest_package_imports():
    module = importlib.import_module("ingest")
    assert module.__name__ == "ingest"