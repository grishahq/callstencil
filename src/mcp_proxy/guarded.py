"""Explicit-policy entry point; compatibility CLI remains available separately."""
from .__main__ import main as bridge_main


def main() -> None:
    """Run the bridge only with a validated explicit policy."""
    bridge_main(require_policy=True)


if __name__ == "__main__":
    main()
