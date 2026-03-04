"""
Example execution script demonstrating best practices.

This script shows the proper pattern for execution layer code:
- Pure, testable logic separated from I/O
- Clear function signatures
- Proper error handling
- Logging for auditability
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Any

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def process_data(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Process a list of records and return results.

    This is pure logic - no I/O, easily testable.

    Args:
        records: List of data records to process

    Returns:
        Dictionary with processed results and metadata
    """
    processed = []
    errors = []

    for idx, record in enumerate(records):
        try:
            # Example validation
            if not record.get("id"):
                errors.append(f"Record {idx}: missing required field 'id'")
                continue

            # Example transformation
            processed_record = {
                "id": record["id"],
                "value": record.get("value", 0) * 2,  # Example transformation
                "processed": True
            }
            processed.append(processed_record)

        except Exception as e:
            errors.append(f"Record {idx}: {str(e)}")
            logger.error(f"Error processing record {idx}: {e}")

    return {
        "processed_records": processed,
        "total_count": len(records),
        "success_count": len(processed),
        "error_count": len(errors),
        "errors": errors
    }


def load_input(file_path: Path) -> List[Dict[str, Any]]:
    """
    Load data from input file.

    This handles I/O - separated from business logic for easier testing.
    """
    logger.info(f"Loading data from {file_path}")

    if not file_path.exists():
        raise FileNotFoundError(f"Input file not found: {file_path}")

    with open(file_path, 'r') as f:
        data = json.load(f)

    logger.info(f"Loaded {len(data)} records")
    return data


def save_output(results: Dict[str, Any], output_path: Path) -> None:
    """
    Save results to output file.

    Handles I/O - separated from business logic.
    """
    logger.info(f"Saving results to {output_path}")

    # Ensure output directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w') as f:
        json.dump(results, f, indent=2)

    logger.info(f"Saved {results['success_count']} processed records")


def main() -> None:
    """
    CLI entry point - handles I/O and orchestration.

    The business logic (process_data) is kept separate and testable.
    """
    import sys

    if len(sys.argv) < 3:
        print("Usage: python example_script.py <input_file> <output_file>")
        sys.exit(1)

    input_file = Path(sys.argv[1])
    output_file = Path(sys.argv[2])

    try:
        # Load, process, save
        records = load_input(input_file)
        results = process_data(records)
        save_output(results, output_file)

        # Report results
        print(f"Processing complete:")
        print(f"  Total records: {results['total_count']}")
        print(f"  Successful: {results['success_count']}")
        print(f"  Errors: {results['error_count']}")

        if results['errors']:
            print("\nErrors:")
            for error in results['errors']:
                print(f"  - {error}")

        # Exit with appropriate code
        sys.exit(0 if results['error_count'] == 0 else 1)

    except Exception as e:
        logger.error(f"Script failed: {e}")
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
