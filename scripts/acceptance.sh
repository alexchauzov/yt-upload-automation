#!/bin/bash
# Acceptance tests entrypoint with mandatory reset
# Linux/macOS version

set -e  # Exit on any error

echo "============================================================"
echo "RESET TEST ENVIRONMENT"
echo "============================================================"
python utils/sheets_reset_verify.py

echo ""
echo "============================================================"
echo "RUN ACCEPTANCE TESTS"
echo "============================================================"
pytest -v -m acceptance --tb=short

echo ""
echo "Acceptance tests completed successfully."
