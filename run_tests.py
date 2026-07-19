#!/usr/bin/env python3
"""
Test runner for Nexus Verification Engine v0.1.1
Executes full test suite before PR submission.
Exits non-zero if zero tests are discovered.
"""

import sys
import unittest
from pathlib import Path

def run_tests():
    """Execute comprehensive test suite."""
    
    print("=" * 80)
    print("NEXUS VERIFICATION ENGINE v0.1.1 - TEST SUITE")
    print("=" * 80)
    print()
    
    # Discover and run tests
    loader = unittest.TestLoader()
    start_dir = Path(__file__).resolve().parent / "tests"
    suite = loader.discover(str(start_dir), pattern='test_*.py')
    
    # Fail immediately if no tests were discovered
    if suite.countTestCases() == 0:
        print("✗ ZERO TESTS DISCOVERED — aborting")
        print()
        print("No test files matching 'test_*.py' were found.")
        print("Ensure test files exist under the tests/ directory.")
        return 2
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    print()
    print("=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Skipped: {len(result.skipped)}")
    print()
    
    if result.wasSuccessful():
        print("✓ ALL TESTS PASSED")
        print()
        print("Implementation ready for review:")
        print("  - Authoritative contract: contracts/NEXUS-CC-CON-001.json")
        print("  - Python engine: verification_engine/")
        print("  - Node.js engine: verification_engine/engine.js")
        print("  - Node.js service: server.js")
        print("  - Fixture tests: fixtures/")
        print("  - Documentation: docs/NEXUS-CC-WF-001.svg, README.md")
        print()
        return 0
    else:
        print("✗ TESTS FAILED")
        print()
        if result.failures:
            print("Failures:")
            for test, traceback in result.failures:
                print(f"  {test}: {traceback}")
        if result.errors:
            print("Errors:")
            for test, traceback in result.errors:
                print(f"  {test}: {traceback}")
        return 1

if __name__ == '__main__':
    sys.exit(run_tests())
