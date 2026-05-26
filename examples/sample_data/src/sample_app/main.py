"""Sample entrypoint."""

from sample_app.utils import greet


def main() -> None:
    print(greet("World"))


if __name__ == "__main__":
    main()
