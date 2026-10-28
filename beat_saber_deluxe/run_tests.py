#!/usr/bin/env python3
"""
OrBeats — Test Harness
=================================
Run unit tests, coverage, and linting from a single command.

Usage:
    python3 run_tests.py                 # Run all tests
    python3 run_tests.py --fast          # Skip slow/integration tests
    python3 run_tests.py --coverage      # Run with coverage report
    python3 run_tests.py --module pipeline  # Test only pipeline module
    python3 run_tests.py --ci            # CI mode (strict, coverage enforced)
    python3 run_tests.py --lint          # Also run linting on tools/
"""
import subprocess
import sys
import os
import argparse
import time

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
TESTS_DIR = os.path.join(PROJECT_ROOT, "tests")
TOOLS_DIR = os.path.join(PROJECT_ROOT, "tools")
PYPROJECT = os.path.join(PROJECT_ROOT, "pyproject.toml")

# Module name -> test file mapping
MODULE_MAP = {
    "pipeline": "test_pipeline.py",
    "pipeline-bugfixes": "test_pipeline_bugfixes.py",
    "hevag": "test_hevag_encoder.py",
    "lapped": "test_lapped_audio.py",
    "inject": "test_inject_pack_bundle.py",
    "patched": "test_patched_pack_bundle.py",
    "replacement": "test_replacement_pack.py",
    "beatsaver": "test_download_beatsaver.py",
    "compatibility": "test_hevag_audio_compatibility.py",
}


def banner(text, width=60):
    print(f"\n{'=' * width}")
    print(f"  {text}")
    print(f"{'=' * width}")


def run_cmd(cmd, cwd=None, env=None):
    """Run a command and return (exit_code, stdout, stderr)."""
    result = subprocess.run(
        cmd, cwd=cwd or PROJECT_ROOT, env=env,
        capture_output=True, text=True
    )
    return result.returncode, result.stdout, result.stderr


def check_tool(name):
    """Check if a CLI tool is available."""
    code, _, _ = run_cmd(["which", name])
    return code == 0


def run_lint(fix=False):
    """Run linting on the tools/ directory."""
    banner("Linting tools/")
    # Try ruff via python -m (more reliable than bare 'ruff' on PATH)
    code, _, _ = run_cmd([sys.executable, "-m", "ruff", "--version"])
    if code == 0:
        cmd = [sys.executable, "-m", "ruff", "check", TOOLS_DIR]
        if fix:
            cmd.append("--fix")
        code, stdout, stderr = run_cmd(cmd)
        print(stdout or stderr)
        return code
    elif check_tool("flake8"):
        cmd = ["flake8", TOOLS_DIR, "--max-line-length=120", "--ignore=E501,E402"]
        if fix:
            cmd = ["autopep8", "--in-place", "--recursive", TOOLS_DIR]
        code, stdout, stderr = run_cmd(cmd)
        print(stdout or stderr)
        return code
    else:
        print("  No linter found (install ruff or flake8). Skipping.")
        return 0


def run_tests(args):
    """Build and execute the pytest command."""
    pytest_args = [sys.executable, "-m", "pytest", TESTS_DIR, "-v", "--tb=short"]

    # Strict mode for CI
    if args.ci:
        pytest_args.append("--strict-markers")
        pytest_args.append("-x")

    # Module filter
    if args.module:
        mod = args.module.lower()
        if mod in MODULE_MAP:
            test_file = os.path.join(TESTS_DIR, MODULE_MAP[mod])
            pytest_args = [sys.executable, "-m", "pytest", test_file, "-v", "--tb=short"]
            print(f"  Testing module: {mod} ({MODULE_MAP[mod]})")
        else:
            print(f"  Unknown module '{mod}'. Available: {', '.join(MODULE_MAP.keys())}")
            return 1

    # Marker filtering
    markers = []
    if args.fast:
        markers.append("not slow")
        markers.append("not integration")
        markers.append("not requires_audio")
    if markers:
        pytest_args.extend(["-m", " and ".join(markers)])

    # Coverage
    if args.coverage or args.ci:
        pytest_args.extend([
            "--cov=tools",
            "--cov-report=term-missing",
            "--cov-report=html:htmlcov",
            "--cov-config=pyproject.toml",
        ])
        if args.ci:
            pytest_args.append("--cov-fail-under=20")

    # Verbosity
    if args.quiet:
        pytest_args.extend(["-q", "--tb=line"])

    print(f"  Command: {' '.join(pytest_args)}")
    print()
    start = time.time()
    code, stdout, stderr = run_cmd(pytest_args)
    elapsed = time.time() - start
    print(stdout)
    if stderr:
        print(stderr, file=sys.stderr)
    print(f"\n  Completed in {elapsed:.1f}s")
    return code


def print_summary(test_code, lint_code):
    """Print final summary."""
    banner("Summary")
    status = []
    if test_code == 0:
        status.append("  Tests:      PASS")
    else:
        status.append("  Tests:      FAIL")
    if lint_code == 0:
        status.append("  Lint:       PASS")
    else:
        status.append("  Lint:       FAIL")

    for s in status:
        print(s)

    overall = 0 if (test_code == 0 and lint_code == 0) else 1
    if overall == 0:
        print("\n  All checks passed!")
    else:
        print("\n  Some checks failed.")
    return overall


def main():
    parser = argparse.ArgumentParser(
        description="OrBeats test harness",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--fast", action="store_true",
                        help="Skip slow/integration/requires_audio tests")
    parser.add_argument("--coverage", action="store_true",
                        help="Run with coverage report")
    parser.add_argument("--module", "-m", default=None,
                        help="Test only a specific module (pipeline, hevag, lapped, ...)")
    parser.add_argument("--verbose", "-V", action="store_true", help="Verbose output")
    parser.add_argument("--quiet", "-q", action="store_true", help="Minimal output")
    parser.add_argument("--lint", action="store_true",
                        help="Also run linting on tools/")
    parser.add_argument("--fix", action="store_true",
                        help="Auto-fix lint issues (implies --lint)")
    parser.add_argument("--ci", action="store_true",
                        help="CI mode: strict, coverage enforced, no interactive")
    args = parser.parse_args()

    if args.fix:
        args.lint = True

    banner("OrBeats — Test Suite")

    # Lint
    lint_code = 0
    if args.lint or args.fix:
        lint_code = run_lint(fix=args.fix)

    # Tests
    test_code = run_tests(args)

    # Summary
    overall = print_summary(test_code, lint_code)
    sys.exit(overall)


if __name__ == "__main__":
    main()
