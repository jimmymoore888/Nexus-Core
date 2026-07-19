#!/usr/bin/env python3
"""
Test runner for Nexus Verification Engine v0.1.1
Executes full test suite before PR submission
"""

import sys
import subprocess
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
    start_dir = str(Path(__file__).parent)
    suite = loader.discover(start_dir, pattern='test_*.py')
    
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
        print("  - Node.js service: server.js")
        print("  - Fixture tests: fixtures/")
        print("  - Documentation: docs/NEXUS-CC-WF-001.svg, README.md")
        print()
        print("Opening pull request to main...")
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
