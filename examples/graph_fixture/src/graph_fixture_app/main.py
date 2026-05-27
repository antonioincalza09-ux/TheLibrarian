"""Application entrypoint for graph fixture."""

from .utils import normalize


class Greeter:
    """Simple greeting component."""

    def greet(self, name: str) -> str:
        return f"Hello {normalize(name)}"


def main() -> str:
    return Greeter().greet("Developer")


if __name__ == "__main__":
    print(main())
