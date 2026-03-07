#!/usr/bin/env python3
"""
Test runner for the Cloud Storage Tiering System assignment.

This script provides a convenient way to run different test suites and generate reports.
"""
import argparse
import subprocess
import sys
import os
from pathlib import Path

def run_tests(test_type, verbose=False, coverage=False):
    """Run the specified test suite."""
    cmd = ["pytest", "-v" if verbose else "-q"]
    
    if coverage:
        cmd.extend([
            "--cov=src",
            "--cov-report=term",
            "--cov-report=xml:coverage.xml"
        ])
    
    if test_type == "all":
        cmd.append("tests/")
    elif test_type == "functional":
        cmd.append("tests/functional/")
    elif test_type == "performance":
        cmd.append("tests/performance/")
    elif test_type == "fault":
        cmd.append("tests/fault_injection/")
    else:
        print(f"Unknown test type: {test_type}")
        return False
    
    print(f"Running {test_type} tests...")
    result = subprocess.run(cmd)
    return result.returncode == 0

def main():
    parser = argparse.ArgumentParser(description="Run tests for the Cloud Storage Tiering System")
    parser.add_argument(
        "test_type",
        nargs="?",
        default="all",
        choices=["all", "functional", "performance", "fault"],
        help="Type of tests to run (default: all)"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose output"
    )
    parser.add_argument(
        "--coverage",
        action="store_true",
        help="Generate coverage report"
    )
    
    args = parser.parse_args()
    
    # Ensure we're in the correct directory
    os.chdir(Path(__file__).parent)
    
    success = run_tests(args.test_type, args.verbose, args.coverage)
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
