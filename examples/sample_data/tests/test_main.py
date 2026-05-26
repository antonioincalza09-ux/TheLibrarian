from sample_app.utils import greet


def test_greet() -> None:
    assert greet("World") == "Hello, World"
