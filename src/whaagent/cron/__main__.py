"""CLI entry point for cron tick."""

import argparse
import logging

from whaagent.cron import tick

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)


def main() -> None:
    """Run the cron tick."""
    parser = argparse.ArgumentParser(description="Execute scheduled tasks")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose logging")
    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    executed = tick()
    if executed > 0:
        print(f"Executed {executed} task(s)")
    else:
        print("No tasks due")


if __name__ == "__main__":
    main()
