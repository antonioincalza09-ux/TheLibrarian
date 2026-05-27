from src.graph_fixture_app.main import main


def test_main() -> None:
    assert main() == "Hello Developer"
