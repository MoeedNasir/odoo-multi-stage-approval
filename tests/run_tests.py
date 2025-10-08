#!/usr/bin/env python3
"""
Test runner script for Multi-Stage Approval System
Run specific test categories or all tests
"""

import sys
import argparse
import subprocess
import logging
import os

logging.basicConfig(level=logging.INFO)
_logger = logging.getLogger(__name__)


def run_tests(test_tags, database, module_name):
    """Run Odoo tests with specified tags"""
    cmd = [
        'odoo-bin',
        '--test-enable',
        '--stop-after-init',
        '-d', database,
        '-i', module_name,
        '--test-tags', test_tags
    ]

    _logger.info("Running tests with tags: %s", test_tags)
    _logger.info("Command: %s", ' '.join(cmd))

    try:
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode == 0:
            _logger.info("✅ Tests passed!")
            if result.stdout:
                _logger.info("Output:\n%s", result.stdout)
            return True
        else:
            _logger.error("❌ Tests failed!")
            if result.stdout:
                _logger.error("STDOUT:\n%s", result.stdout)
            if result.stderr:
                _logger.error("STDERR:\n%s", result.stderr)
            return False

    except Exception as e:
        _logger.error("Error running tests: %s", str(e))
        return False


def run_specific_test_file(test_file, database, module_name):
    """Run specific test file"""
    cmd = [
        'odoo-bin',
        '--test-enable',
        '--stop-after-init',
        '-d', database,
        '-i', module_name,
        '--log-level=test',
        '--test-file', test_file
    ]

    _logger.info("Running test file: %s", test_file)

    try:
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode == 0:
            _logger.info("✅ Test file passed!")
            return True
        else:
            _logger.error("❌ Test file failed!")
            if result.stderr:
                _logger.error("STDERR:\n%s", result.stderr)
            return False

    except Exception as e:
        _logger.error("Error running test file: %s", str(e))
        return False


def main():
    parser = argparse.ArgumentParser(description='Run Multi-Stage Approval System Tests')
    parser.add_argument('--database', '-d', default='test_db', help='Database name')
    parser.add_argument('--module', '-m', default='multi_stage_approval', help='Module name')
    parser.add_argument('--type', '-t', choices=['all', 'integration', 'performance', 'edge', 'specific'],
                        default='all', help='Test type to run')
    parser.add_argument('--file', '-f', help='Specific test file to run')

    args = parser.parse_args()

    test_configs = {
        'all': 'integration,performance,edge_cases',
        'integration': 'integration',
        'performance': 'performance',
        'edge': 'edge_cases',
        'specific': 'integration,performance,edge_cases'  # For specific file runs
    }

    if args.type == 'specific' and args.file:
        success = run_specific_test_file(args.file, args.database, args.module)
    else:
        test_tags = test_configs[args.type]
        success = run_tests(test_tags, args.database, args.module)

    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()