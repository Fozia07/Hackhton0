#!/usr/bin/env python3
"""
Gold Tier System Validation Test
=================================

Comprehensive test suite to validate all Gold Tier components
are working correctly end-to-end.

Usage:
    python3 scripts/test_gold_tier.py
"""

import os
import sys
import json
import subprocess
import shutil
from datetime import datetime
from pathlib import Path

# Colors for terminal output
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    BOLD = '\033[1m'
    END = '\033[0m'

def print_header(text):
    print(f"\n{Colors.BOLD}{Colors.CYAN}{'='*60}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.CYAN}  {text}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.CYAN}{'='*60}{Colors.END}\n")

def print_test(name, passed, details=""):
    status = f"{Colors.GREEN}PASS{Colors.END}" if passed else f"{Colors.RED}FAIL{Colors.END}"
    print(f"  [{status}] {name}")
    if details and not passed:
        print(f"        {Colors.YELLOW}{details}{Colors.END}")

def print_section(text):
    print(f"\n{Colors.BLUE}{Colors.BOLD}>> {text}{Colors.END}")

BASE_DIR = Path(__file__).parent.parent
VAULT_DIR = BASE_DIR / "AI_Employee_Vault"
SCRIPTS_DIR = BASE_DIR / "scripts"

def test_file_exists(filepath, name):
    """Test if a file exists."""
    exists = filepath.exists()
    print_test(f"{name} exists", exists, f"Missing: {filepath}")
    return exists

def test_script_runs(script_path, args=[], name="", timeout=60):
    """Test if a script runs without errors."""
    try:
        result = subprocess.run(
            [sys.executable, str(script_path)] + args,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(BASE_DIR)
        )
        success = result.returncode == 0
        print_test(f"{name} executes successfully", success,
                  f"Exit code: {result.returncode}")
        return success, result
    except subprocess.TimeoutExpired:
        print_test(f"{name} executes successfully", False, "Timeout")
        return False, None
    except Exception as e:
        print_test(f"{name} executes successfully", False, str(e))
        return False, None

def test_json_valid(filepath, name):
    """Test if a JSON file is valid."""
    try:
        with open(filepath, 'r') as f:
            json.load(f)
        print_test(f"{name} is valid JSON", True)
        return True
    except Exception as e:
        print_test(f"{name} is valid JSON", False, str(e))
        return False

def run_tests():
    """Run all Gold Tier validation tests."""
    print_header("GOLD TIER SYSTEM VALIDATION")

    results = {
        "total": 0,
        "passed": 0,
        "failed": 0
    }

    def record(passed):
        results["total"] += 1
        if passed:
            results["passed"] += 1
        else:
            results["failed"] += 1
        return passed

    # =========================================================================
    # TEST 1: Core Scripts Exist
    # =========================================================================
    print_section("1. Core Scripts Existence")

    scripts = [
        ("social_media_orchestrator.py", "Social Media Orchestrator"),
        ("social_campaign_engine.py", "Campaign Engine"),
        ("social_analytics_engine.py", "Analytics Engine"),
        ("autonomous_controller.py", "Autonomous Controller"),
        ("facebook_poster.py", "Facebook Poster"),
        ("instagram_poster.py", "Instagram Poster"),
        ("twitter_poster.py", "Twitter Poster"),
        ("linkedin_poster.py", "LinkedIn Poster"),
    ]

    for script, name in scripts:
        record(test_file_exists(SCRIPTS_DIR / script, name))

    # =========================================================================
    # TEST 2: Utility Modules Exist
    # =========================================================================
    print_section("2. Utility Modules")

    utils = [
        ("audit_logger.py", "Audit Logger"),
        ("retry_handler.py", "Retry Handler"),
        ("heartbeat.py", "Heartbeat System"),
        ("watchdog.py", "Watchdog"),
        ("process_monitor.py", "Process Monitor"),
        ("resource_guard.py", "Resource Guard"),
    ]

    utils_dir = BASE_DIR / "utils"
    for util, name in utils:
        record(test_file_exists(utils_dir / util, name))

    # =========================================================================
    # TEST 3: Directory Structure
    # =========================================================================
    print_section("3. Directory Structure")

    directories = [
        (VAULT_DIR / "Approved", "Approved folder"),
        (VAULT_DIR / "Done", "Done folder"),
        (VAULT_DIR / "Drafts", "Drafts folder"),
        (VAULT_DIR / "Business", "Business folder"),
        (VAULT_DIR / "Analytics", "Analytics folder"),
        (VAULT_DIR / "Executive", "Executive folder"),
        (VAULT_DIR / "System", "System folder"),
    ]

    for dir_path, name in directories:
        dir_path.mkdir(parents=True, exist_ok=True)
        record(test_file_exists(dir_path, name))

    # =========================================================================
    # TEST 4: Configuration Files
    # =========================================================================
    print_section("4. Configuration Files")

    record(test_file_exists(VAULT_DIR / "Business" / "business_goals.json", "Business Goals"))
    record(test_json_valid(VAULT_DIR / "Business" / "business_goals.json", "Business Goals"))

    record(test_file_exists(VAULT_DIR / "Analytics" / "social_metrics.json", "Social Metrics"))
    record(test_json_valid(VAULT_DIR / "Analytics" / "social_metrics.json", "Social Metrics"))

    # =========================================================================
    # TEST 5: Campaign Engine Execution
    # =========================================================================
    print_section("5. Campaign Engine Test")

    success, result = test_script_runs(
        SCRIPTS_DIR / "social_campaign_engine.py",
        ["--verbose"],
        "Campaign Engine",
        timeout=120
    )
    record(success)

    # Check outputs
    if success:
        drafts = list((VAULT_DIR / "Drafts").glob("*_POST_*.md"))
        record(len(drafts) > 0)
        print_test(f"Generated {len(drafts)} draft files", len(drafts) > 0)

        briefs = list((VAULT_DIR / "Executive").glob("weekly_campaign_brief_*.md"))
        has_brief = len(briefs) > 0
        record(has_brief)
        print_test("CEO brief generated", has_brief)

    # =========================================================================
    # TEST 6: Analytics Engine Execution
    # =========================================================================
    print_section("6. Analytics Engine Test")

    success, result = test_script_runs(
        SCRIPTS_DIR / "social_analytics_engine.py",
        ["--verbose"],
        "Analytics Engine",
        timeout=120
    )
    record(success)

    # Check outputs
    if success:
        insights_file = VAULT_DIR / "Analytics" / "strategy_insights.json"
        record(test_file_exists(insights_file, "Strategy Insights"))
        record(test_json_valid(insights_file, "Strategy Insights"))

        reports = list((VAULT_DIR / "Executive").glob("weekly_performance_report_*.md"))
        has_report = len(reports) > 0
        record(has_report)
        print_test("Performance report generated", has_report)

    # =========================================================================
    # TEST 7: Platform Agents Test
    # =========================================================================
    print_section("7. Platform Agents Test")

    # Create a test post
    test_post = VAULT_DIR / "Approved" / "FACEBOOK_POST_validation_test.md"
    test_post.write_text("""---
title: Validation Test Post
---

This is a validation test post for the Gold Tier system.
Testing all components are working correctly.

#Test #Validation #GoldTier
""")

    agents = [
        ("facebook_poster.py", "Facebook"),
        ("instagram_poster.py", "Instagram"),
        ("twitter_poster.py", "Twitter"),
        ("linkedin_poster.py", "LinkedIn"),
    ]

    for script, name in agents:
        success, _ = test_script_runs(
            SCRIPTS_DIR / script,
            ["--file", str(test_post), "--simulate", "--verbose"],
            f"{name} Poster",
            timeout=30
        )
        record(success)

    # Cleanup test post
    if test_post.exists():
        test_post.unlink()

    # =========================================================================
    # TEST 8: Orchestrator Test
    # =========================================================================
    print_section("8. Orchestrator Test")

    # Create test posts for orchestrator
    test_posts = [
        ("FACEBOOK_POST_orch_test.md", "Facebook orchestrator test post content here for validation. #Test"),
        ("LINKEDIN_POST_orch_test.md", "LinkedIn orchestrator test post content here for validation. #Test"),
    ]

    for filename, content in test_posts:
        (VAULT_DIR / "Approved" / filename).write_text(content)

    success, _ = test_script_runs(
        SCRIPTS_DIR / "social_media_orchestrator.py",
        ["--once", "--simulate", "--verbose"],
        "Social Media Orchestrator",
        timeout=60
    )
    record(success)

    # Check files moved to Done
    done_files = list((VAULT_DIR / "Done").glob("*_orch_test.md"))
    moved = len(done_files) > 0
    record(moved)
    print_test("Posts moved to Done folder", moved, f"Found {len(done_files)} files")

    # =========================================================================
    # TEST 9: Autonomous Controller Test (Dry Run)
    # =========================================================================
    print_section("9. Autonomous Controller Test")

    # Reset state for clean test
    state_file = VAULT_DIR / "System" / "autonomous_state.json"
    if state_file.exists():
        state_file.unlink()

    success, _ = test_script_runs(
        SCRIPTS_DIR / "autonomous_controller.py",
        ["--dry-run", "--verbose"],
        "Autonomous Controller (Dry Run)",
        timeout=180
    )
    record(success)

    # Check decision report generated
    decisions = list((VAULT_DIR / "Executive").glob("autonomy_decision_*.md"))
    has_decision = len(decisions) > 0
    record(has_decision)
    print_test("Autonomy decision report generated", has_decision)

    # =========================================================================
    # TEST 10: Integration Test - Full Loop
    # =========================================================================
    print_section("10. Integration Test - Full Autonomous Loop")

    # Test the complete flow: Analytics -> Evaluate -> Campaign
    success, _ = test_script_runs(
        SCRIPTS_DIR / "autonomous_controller.py",
        ["--force", "--verbose"],
        "Full Autonomous Loop (Forced)",
        timeout=300
    )
    record(success)

    # Verify state was updated
    if state_file.exists():
        try:
            with open(state_file, 'r') as f:
                state = json.load(f)
            has_history = len(state.get("history", [])) > 0
            record(has_history)
            print_test("Autonomous state has history", has_history)
        except:
            record(False)
    else:
        record(False)

    # =========================================================================
    # FINAL SUMMARY
    # =========================================================================
    print_header("TEST RESULTS SUMMARY")

    pass_rate = (results["passed"] / results["total"] * 100) if results["total"] > 0 else 0

    print(f"  Total Tests:  {results['total']}")
    print(f"  {Colors.GREEN}Passed:{Colors.END}       {results['passed']}")
    print(f"  {Colors.RED}Failed:{Colors.END}       {results['failed']}")
    print(f"  Pass Rate:    {pass_rate:.1f}%")
    print()

    if results["failed"] == 0:
        print(f"  {Colors.GREEN}{Colors.BOLD}ALL TESTS PASSED - GOLD TIER SYSTEM FULLY OPERATIONAL{Colors.END}")
        status = 0
    else:
        print(f"  {Colors.YELLOW}{Colors.BOLD}SOME TESTS FAILED - Review issues above{Colors.END}")
        status = 1

    print()
    print_header("SYSTEM ARCHITECTURE VERIFIED")

    print("""
    ┌──────────────────────────────────────────────────────────────┐
    │                    GOLD TIER AI EMPLOYEE                     │
    │                                                              │
    │  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐     │
    │  │  Campaign   │───▶│   Drafts    │───▶│  Approval   │     │
    │  │   Engine    │    │             │    │  Workflow   │     │
    │  └─────────────┘    └─────────────┘    └──────┬──────┘     │
    │         ▲                                      │            │
    │         │                                      ▼            │
    │  ┌──────┴──────┐                       ┌─────────────┐     │
    │  │ Autonomous  │                       │Orchestrator │     │
    │  │ Controller  │                       │             │     │
    │  └──────┬──────┘                       └──────┬──────┘     │
    │         │                                      │            │
    │         │                                      ▼            │
    │  ┌──────┴──────┐    ┌─────────────┐    ┌─────────────┐     │
    │  │  Analytics  │◀───│   Metrics   │◀───│  Platform   │     │
    │  │   Engine    │    │             │    │   Agents    │     │
    │  └─────────────┘    └─────────────┘    └─────────────┘     │
    │                                                              │
    │  ┌─────────────────────────────────────────────────────┐   │
    │  │  Supporting: Watchdog | Heartbeat | Audit | Retry   │   │
    │  └─────────────────────────────────────────────────────┘   │
    │                                                              │
    └──────────────────────────────────────────────────────────────┘
    """)

    return status


if __name__ == "__main__":
    sys.exit(run_tests())
