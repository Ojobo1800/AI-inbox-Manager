#!/bin/bash
# Format all Python code

echo "Formatting Python code with black..."
black execution/ services/ tests/

echo "Done!"
