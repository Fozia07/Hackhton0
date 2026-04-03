#!/usr/bin/env python3
"""
Playwright Automation Helper
Gold Tier - Real Browser Automation

Provides browser automation utilities for social media posting.
Handles login, posting, and error recovery for Facebook and LinkedIn.
"""

import os
import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, Tuple
from dataclasses import dataclass
from enum import Enum

# Configure logging
logger = logging.getLogger("playwright_automation")


class Platform(Enum):
    FACEBOOK = "facebook"
    LINKEDIN = "linkedin"


@dataclass
class AutomationResult:
    """Result of an automation operation"""
    success: bool
    platform: str
    action: str
    message: str
    screenshot_path: Optional[str] = None
    error: Optional[str] = None
    timestamp: str = None

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "platform": self.platform,
            "action": self.action,
            "message": self.message,
            "screenshot_path": self.screenshot_path,
            "error": self.error,
            "timestamp": self.timestamp
        }


class PlaywrightAutomation:
    """
    Browser automation using Playwright.

    Handles:
    - Browser lifecycle management
    - Platform-specific login flows
    - Post creation and publishing
    - Error capture and recovery
    """

    # Timeouts in milliseconds
    DEFAULT_TIMEOUT = 30000
    NAVIGATION_TIMEOUT = 60000
    ACTION_TIMEOUT = 10000

    def __init__(
        self,
        platform: Platform,
        headless: bool = False,
        log_path: Optional[Path] = None
    ):
        self.platform = platform
        self.headless = headless
        self.log_path = log_path or Path("AI_Employee_Vault/Logs")
        self.log_path.mkdir(parents=True, exist_ok=True)

        self.browser = None
        self.context = None
        self.page = None

        # Platform URLs
        self.urls = {
            Platform.FACEBOOK: {
                "login": "https://www.facebook.com/login",
                "home": "https://www.facebook.com",
            },
            Platform.LINKEDIN: {
                "login": "https://www.linkedin.com/login",
                "home": "https://www.linkedin.com/feed/",
            }
        }

    def _log_event(self, event_type: str, details: Dict[str, Any]):
        """Log automation event to file"""
        log_file = self.log_path / f"{self.platform.value}_automation.log"
        entry = {
            "timestamp": datetime.now().isoformat(),
            "event": event_type,
            "platform": self.platform.value,
            "details": details
        }
        with open(log_file, 'a') as f:
            f.write(json.dumps(entry) + "\n")

    async def start_browser(self) -> bool:
        """Initialize Playwright browser"""
        try:
            from playwright.async_api import async_playwright

            self._playwright = await async_playwright().start()
            self.browser = await self._playwright.chromium.launch(
                headless=self.headless,
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--disable-infobars',
                    '--no-sandbox'
                ]
            )

            # Create context with realistic settings
            self.context = await self.browser.new_context(
                viewport={'width': 1280, 'height': 800},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                locale='en-US',
                timezone_id='America/New_York'
            )

            self.page = await self.context.new_page()
            self.page.set_default_timeout(self.DEFAULT_TIMEOUT)

            self._log_event("browser_started", {"headless": self.headless})
            logger.info(f"Browser started for {self.platform.value}")
            return True

        except ImportError:
            logger.error("Playwright not installed. Run: pip install playwright && playwright install chromium")
            return False
        except Exception as e:
            logger.error(f"Failed to start browser: {e}")
            self._log_event("browser_error", {"error": str(e)})
            return False

    async def close_browser(self):
        """Close browser and cleanup"""
        try:
            if self.context:
                await self.context.close()
            if self.browser:
                await self.browser.close()
            if hasattr(self, '_playwright'):
                await self._playwright.stop()

            self._log_event("browser_closed", {})
            logger.info("Browser closed")
        except Exception as e:
            logger.warning(f"Error closing browser: {e}")

    async def _take_screenshot(self, name: str) -> Optional[str]:
        """Take screenshot for debugging"""
        try:
            screenshot_dir = self.log_path / "screenshots"
            screenshot_dir.mkdir(parents=True, exist_ok=True)

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            path = screenshot_dir / f"{self.platform.value}_{name}_{timestamp}.png"

            await self.page.screenshot(path=str(path))
            return str(path)
        except Exception as e:
            logger.warning(f"Screenshot failed: {e}")
            return None

    async def _wait_and_click(self, selector: str, timeout: int = None) -> bool:
        """Wait for element and click it"""
        try:
            timeout = timeout or self.ACTION_TIMEOUT
            element = await self.page.wait_for_selector(selector, timeout=timeout)
            if element:
                await element.click()
                return True
        except Exception as e:
            logger.warning(f"Click failed for {selector}: {e}")
        return False

    async def _wait_and_fill(self, selector: str, text: str, timeout: int = None) -> bool:
        """Wait for element and fill it with text"""
        try:
            timeout = timeout or self.ACTION_TIMEOUT
            element = await self.page.wait_for_selector(selector, timeout=timeout)
            if element:
                await element.fill(text)
                return True
        except Exception as e:
            logger.warning(f"Fill failed for {selector}: {e}")
        return False

    # =========================================================================
    # Facebook Automation
    # =========================================================================

    async def _find_and_fill(self, selectors: list, text: str, field_name: str) -> bool:
        """Try multiple selectors to find and fill a field"""
        for selector in selectors:
            try:
                logger.info(f"Trying selector for {field_name}: {selector}")
                element = await self.page.wait_for_selector(selector, timeout=5000)
                if element:
                    await element.fill(text)
                    logger.info(f"Successfully filled {field_name} using: {selector}")
                    return True
            except Exception as e:
                logger.debug(f"Selector {selector} failed: {e}")
                continue
        logger.error(f"All selectors failed for {field_name}")
        return False

    async def _find_and_click(self, selectors: list, button_name: str) -> bool:
        """Try multiple selectors to find and click a button"""
        for selector in selectors:
            try:
                logger.info(f"Trying selector for {button_name}: {selector}")
                element = await self.page.wait_for_selector(selector, timeout=5000)
                if element:
                    await element.click()
                    logger.info(f"Successfully clicked {button_name} using: {selector}")
                    return True
            except Exception as e:
                logger.debug(f"Selector {selector} failed: {e}")
                continue
        logger.error(f"All selectors failed for {button_name}")
        return False

    async def facebook_login(self, email: str, password: str) -> AutomationResult:
        """Login to Facebook with improved selectors and fallbacks"""
        try:
            logger.info("="*50)
            logger.info("FACEBOOK LOGIN - Starting")
            logger.info("="*50)

            # Navigate to login page
            logger.info(f"Navigating to: {self.urls[Platform.FACEBOOK]['login']}")
            await self.page.goto(
                self.urls[Platform.FACEBOOK]["login"],
                timeout=self.NAVIGATION_TIMEOUT,
                wait_until='domcontentloaded'
            )

            # Wait for page to fully load (30 seconds max)
            logger.info("Waiting for page to load...")
            await self.page.wait_for_load_state('networkidle', timeout=30000)
            await self.page.wait_for_timeout(2000)  # Extra wait for dynamic content

            # Take screenshot of login page
            await self._take_screenshot("login_page_loaded")
            logger.info(f"Current URL: {self.page.url}")

            # Email field selectors (primary and fallbacks)
            email_selectors = [
                'input[name="email"]',
                'input#email',
                'input[type="email"]',
                'input[data-testid="royal_email"]',
                '#email',
            ]

            # Password field selectors (primary and fallbacks)
            password_selectors = [
                'input[name="pass"]',
                'input#pass',
                'input[type="password"]',
                'input[data-testid="royal_pass"]',
                '#pass',
            ]

            # Login button selectors (primary and fallbacks)
            login_button_selectors = [
                'button[name="login"]',
                'button[type="submit"]',
                'button[data-testid="royal_login_button"]',
                'input[type="submit"]',
                '#loginbutton',
                'button:has-text("Log In")',
                'button:has-text("Log in")',
                'div[role="button"]:has-text("Log In")', 
                'div[role="button"]:has-text("Log in")',
            ]

            # Fill email
            logger.info("Filling email field...")
            email_filled = await self._find_and_fill(email_selectors, email, "email")
            if not email_filled:
                screenshot = await self._take_screenshot("email_field_not_found")
                self._log_event("login_failed", {"reason": "email_field_not_found"})
                return AutomationResult(
                    success=False,
                    platform="facebook",
                    action="login",
                    message="Could not find email input field",
                    screenshot_path=screenshot,
                    error="Email field not found"
                )

            # Small delay between fields
            await self.page.wait_for_timeout(500)

            # Fill password
            logger.info("Filling password field...")
            password_filled = await self._find_and_fill(password_selectors, password, "password")
            if not password_filled:
                screenshot = await self._take_screenshot("password_field_not_found")
                self._log_event("login_failed", {"reason": "password_field_not_found"})
                return AutomationResult(
                    success=False,
                    platform="facebook",
                    action="login",
                    message="Could not find password input field",
                    screenshot_path=screenshot,
                    error="Password field not found"
                )

            # Small delay before clicking login
            await self.page.wait_for_timeout(500)

            # Take screenshot before clicking login
            await self._take_screenshot("before_login_click")

            # Click login button
            logger.info("Clicking login button...")
            login_clicked = await self._find_and_click(login_button_selectors, "login button")
            if not login_clicked:
                screenshot = await self._take_screenshot("login_button_not_found")
                self._log_event("login_failed", {"reason": "login_button_not_found"})
                return AutomationResult(
                    success=False,
                    platform="facebook",
                    action="login",
                    message="Could not find login button",
                    screenshot_path=screenshot,
                    error="Login button not found"
                )

            # Wait for navigation after login (30 seconds)
            logger.info("Waiting for login to complete...")
            await self.page.wait_for_load_state('networkidle', timeout=30000)
            await self.page.wait_for_timeout(3000)  # Extra wait for redirect

            # Take screenshot after login attempt
            await self._take_screenshot("after_login_attempt")

            # Check if login successful
            current_url = self.page.url
            logger.info(f"Post-login URL: {current_url}")

            # Check for failure indicators
            if "login" in current_url.lower() or "checkpoint" in current_url.lower():
                screenshot = await self._take_screenshot("login_failed")
                self._log_event("login_failed", {"url": current_url})
                return AutomationResult(
                    success=False,
                    platform="facebook",
                    action="login",
                    message="Login failed - check credentials or security checkpoint",
                    screenshot_path=screenshot,
                    error="Authentication failed"
                )

            self._log_event("login_success", {"url": current_url})
            logger.info("="*50)
            logger.info("FACEBOOK LOGIN - Success!")
            logger.info("="*50)

            return AutomationResult(
                success=True,
                platform="facebook",
                action="login",
                message="Login successful"
            )

        except Exception as e:
            screenshot = await self._take_screenshot("login_error")
            self._log_event("login_error", {"error": str(e)})
            return AutomationResult(
                success=False,
                platform="facebook",
                action="login",
                message=f"Login error: {str(e)}",
                screenshot_path=screenshot,
                error=str(e)
            )

    async def facebook_post(self, content: str) -> AutomationResult:
        """Create and publish a Facebook post"""
        try:
            logger.info("Creating Facebook post...")

            # Navigate to home feed
            await self.page.goto(
                self.urls[Platform.FACEBOOK]["home"],
                timeout=self.NAVIGATION_TIMEOUT
            )
            await self.page.wait_for_load_state('networkidle')

            # Wait a bit for dynamic content
            await self.page.wait_for_timeout(2000)

            # Find and click the "What's on your mind?" box
            # Facebook uses various selectors, try multiple
            create_post_selectors = [
                '[aria-label="Create a post"]',
                '[aria-label="What\'s on your mind?"]',
                'div[role="button"]:has-text("What\'s on your mind")',
                '[data-pagelet="FeedComposer"]',
            ]

            clicked = False
            for selector in create_post_selectors:
                try:
                    element = await self.page.wait_for_selector(selector, timeout=5000)
                    if element:
                        await element.click()
                        clicked = True
                        break
                except:
                    continue

            if not clicked:
                screenshot = await self._take_screenshot("create_post_not_found")
                return AutomationResult(
                    success=False,
                    platform="facebook",
                    action="post",
                    message="Could not find create post button",
                    screenshot_path=screenshot,
                    error="Element not found"
                )

            # Wait for post dialog
            await self.page.wait_for_timeout(2000)

            # Find the text input area in the post dialog
            text_input_selectors = [
                '[aria-label="What\'s on your mind?"][role="textbox"]',
                'div[role="textbox"][contenteditable="true"]',
                '[data-lexical-editor="true"]',
            ]

            typed = False
            for selector in text_input_selectors:
                try:
                    element = await self.page.wait_for_selector(selector, timeout=5000)
                    if element:
                        await element.click()
                        await self.page.keyboard.type(content, delay=50)
                        typed = True
                        break
                except:
                    continue

            if not typed:
                screenshot = await self._take_screenshot("text_input_not_found")
                return AutomationResult(
                    success=False,
                    platform="facebook",
                    action="post",
                    message="Could not find text input",
                    screenshot_path=screenshot,
                    error="Text input not found"
                )

            # Wait a moment for content to register
            await self.page.wait_for_timeout(1000)

            # Find and click Post button
            post_button_selectors = [
                '[aria-label="Post"]',
                'div[role="button"]:has-text("Post")',
                'button:has-text("Post")',
            ]

            posted = False
            for selector in post_button_selectors:
                try:
                    element = await self.page.wait_for_selector(selector, timeout=5000)
                    if element:
                        await element.click()
                        posted = True
                        break
                except:
                    continue

            if not posted:
                screenshot = await self._take_screenshot("post_button_not_found")
                return AutomationResult(
                    success=False,
                    platform="facebook",
                    action="post",
                    message="Could not find post button",
                    screenshot_path=screenshot,
                    error="Post button not found"
                )

            # Wait for post to be submitted
            await self.page.wait_for_timeout(5000)

            screenshot = await self._take_screenshot("post_success")
            self._log_event("post_published", {"content_length": len(content)})
            logger.info("Facebook post published successfully")

            return AutomationResult(
                success=True,
                platform="facebook",
                action="post",
                message="Post published successfully",
                screenshot_path=screenshot
            )

        except Exception as e:
            screenshot = await self._take_screenshot("post_error")
            self._log_event("post_error", {"error": str(e)})
            return AutomationResult(
                success=False,
                platform="facebook",
                action="post",
                message=f"Post error: {str(e)}",
                screenshot_path=screenshot,
                error=str(e)
            )

    # =========================================================================
    # LinkedIn Automation
    # =========================================================================

    async def linkedin_login(self, email: str, password: str) -> AutomationResult:
        """Login to LinkedIn"""
        try:
            logger.info("Attempting LinkedIn login...")
            await self.page.goto(
                self.urls[Platform.LINKEDIN]["login"],
                timeout=self.NAVIGATION_TIMEOUT
            )

            await self.page.wait_for_load_state('networkidle')

            # Fill credentials
            await self._wait_and_fill('#username', email)
            await self._wait_and_fill('#password', password)

            # Click sign in button
            await self._wait_and_click('button[type="submit"]')

            # Wait for navigation
            await self.page.wait_for_load_state('networkidle', timeout=self.NAVIGATION_TIMEOUT)

            # Check if login successful
            current_url = self.page.url
            if "login" in current_url.lower() or "challenge" in current_url.lower():
                screenshot = await self._take_screenshot("login_failed")
                self._log_event("login_failed", {"url": current_url})
                return AutomationResult(
                    success=False,
                    platform="linkedin",
                    action="login",
                    message="Login failed - check credentials or security challenge",
                    screenshot_path=screenshot,
                    error="Authentication failed"
                )

            self._log_event("login_success", {"url": current_url})
            logger.info("LinkedIn login successful")

            return AutomationResult(
                success=True,
                platform="linkedin",
                action="login",
                message="Login successful"
            )

        except Exception as e:
            screenshot = await self._take_screenshot("login_error")
            self._log_event("login_error", {"error": str(e)})
            return AutomationResult(
                success=False,
                platform="linkedin",
                action="login",
                message=f"Login error: {str(e)}",
                screenshot_path=screenshot,
                error=str(e)
            )

    async def linkedin_post(self, content: str) -> AutomationResult:
        """Create and publish a LinkedIn post"""
        try:
            logger.info("Creating LinkedIn post...")

            # Navigate to feed
            await self.page.goto(
                self.urls[Platform.LINKEDIN]["home"],
                timeout=self.NAVIGATION_TIMEOUT
            )
            await self.page.wait_for_load_state('networkidle')
            await self.page.wait_for_timeout(2000)

            # Find and click "Start a post" button
            start_post_selectors = [
                'button:has-text("Start a post")',
                '[aria-label="Text editor for creating content"]',
                '.share-box-feed-entry__trigger',
                'button.artdeco-button--muted',
            ]

            clicked = False
            for selector in start_post_selectors:
                try:
                    element = await self.page.wait_for_selector(selector, timeout=5000)
                    if element:
                        await element.click()
                        clicked = True
                        break
                except:
                    continue

            if not clicked:
                screenshot = await self._take_screenshot("start_post_not_found")
                return AutomationResult(
                    success=False,
                    platform="linkedin",
                    action="post",
                    message="Could not find start post button",
                    screenshot_path=screenshot,
                    error="Element not found"
                )

            # Wait for post modal
            await self.page.wait_for_timeout(2000)

            # Find text editor and type content
            text_editor_selectors = [
                '[aria-label="Text editor for creating content"]',
                '.ql-editor',
                'div[role="textbox"][contenteditable="true"]',
                '.editor-content',
            ]

            typed = False
            for selector in text_editor_selectors:
                try:
                    element = await self.page.wait_for_selector(selector, timeout=5000)
                    if element:
                        await element.click()
                        await self.page.keyboard.type(content, delay=30)
                        typed = True
                        break
                except:
                    continue

            if not typed:
                screenshot = await self._take_screenshot("text_editor_not_found")
                return AutomationResult(
                    success=False,
                    platform="linkedin",
                    action="post",
                    message="Could not find text editor",
                    screenshot_path=screenshot,
                    error="Text editor not found"
                )

            await self.page.wait_for_timeout(1000)

            # Find and click Post button
            post_button_selectors = [
                'button:has-text("Post")',
                '.share-actions__primary-action',
                'button.share-box__submit-btn',
            ]

            posted = False
            for selector in post_button_selectors:
                try:
                    element = await self.page.wait_for_selector(selector, timeout=5000)
                    if element:
                        await element.click()
                        posted = True
                        break
                except:
                    continue

            if not posted:
                screenshot = await self._take_screenshot("post_button_not_found")
                return AutomationResult(
                    success=False,
                    platform="linkedin",
                    action="post",
                    message="Could not find post button",
                    screenshot_path=screenshot,
                    error="Post button not found"
                )

            # Wait for post submission
            await self.page.wait_for_timeout(5000)

            screenshot = await self._take_screenshot("post_success")
            self._log_event("post_published", {"content_length": len(content)})
            logger.info("LinkedIn post published successfully")

            return AutomationResult(
                success=True,
                platform="linkedin",
                action="post",
                message="Post published successfully",
                screenshot_path=screenshot
            )

        except Exception as e:
            screenshot = await self._take_screenshot("post_error")
            self._log_event("post_error", {"error": str(e)})
            return AutomationResult(
                success=False,
                platform="linkedin",
                action="post",
                message=f"Post error: {str(e)}",
                screenshot_path=screenshot,
                error=str(e)
            )


# =============================================================================
# Synchronous Wrapper Functions
# =============================================================================

def run_facebook_automation(
    content: str,
    email: Optional[str] = None,
    password: Optional[str] = None,
    headless: bool = False
) -> AutomationResult:
    """
    Run Facebook automation synchronously.

    Args:
        content: Post content to publish
        email: Facebook email (or from FACEBOOK_EMAIL env var)
        password: Facebook password (or from FACEBOOK_PASSWORD env var)
        headless: Run browser in headless mode

    Returns:
        AutomationResult with success status
    """
    import asyncio

    email = email or os.environ.get('FACEBOOK_EMAIL')
    password = password or os.environ.get('FACEBOOK_PASSWORD')

    if not email or not password:
        return AutomationResult(
            success=False,
            platform="facebook",
            action="setup",
            message="Missing credentials",
            error="FACEBOOK_EMAIL and FACEBOOK_PASSWORD environment variables required"
        )

    async def _run():
        automation = PlaywrightAutomation(Platform.FACEBOOK, headless=headless)

        try:
            if not await automation.start_browser():
                return AutomationResult(
                    success=False,
                    platform="facebook",
                    action="setup",
                    message="Failed to start browser",
                    error="Browser initialization failed"
                )

            # Login
            login_result = await automation.facebook_login(email, password)
            if not login_result.success:
                return login_result

            # Post
            post_result = await automation.facebook_post(content)
            return post_result

        finally:
            await automation.close_browser()

    return asyncio.run(_run())


def run_linkedin_automation(
    content: str,
    email: Optional[str] = None,
    password: Optional[str] = None,
    headless: bool = False
) -> AutomationResult:
    """
    Run LinkedIn automation synchronously.

    Args:
        content: Post content to publish
        email: LinkedIn email (or from LINKEDIN_EMAIL env var)
        password: LinkedIn password (or from LINKEDIN_PASSWORD env var)
        headless: Run browser in headless mode

    Returns:
        AutomationResult with success status
    """
    import asyncio

    email = email or os.environ.get('LINKEDIN_EMAIL')
    password = password or os.environ.get('LINKEDIN_PASSWORD')

    if not email or not password:
        return AutomationResult(
            success=False,
            platform="linkedin",
            action="setup",
            message="Missing credentials",
            error="LINKEDIN_EMAIL and LINKEDIN_PASSWORD environment variables required"
        )

    async def _run():
        automation = PlaywrightAutomation(Platform.LINKEDIN, headless=headless)

        try:
            if not await automation.start_browser():
                return AutomationResult(
                    success=False,
                    platform="linkedin",
                    action="setup",
                    message="Failed to start browser",
                    error="Browser initialization failed"
                )

            # Login
            login_result = await automation.linkedin_login(email, password)
            if not login_result.success:
                return login_result

            # Post
            post_result = await automation.linkedin_post(content)
            return post_result

        finally:
            await automation.close_browser()

    return asyncio.run(_run())


if __name__ == "__main__":
    # Test mode
    import argparse

    parser = argparse.ArgumentParser(description="Playwright Automation Test")
    parser.add_argument("--platform", choices=["facebook", "linkedin"], required=True)
    parser.add_argument("--content", default="Test post from AI Employee System")
    parser.add_argument("--headless", action="store_true")

    args = parser.parse_args()

    print(f"Testing {args.platform} automation...")

    if args.platform == "facebook":
        result = run_facebook_automation(args.content, headless=args.headless)
    else:
        result = run_linkedin_automation(args.content, headless=args.headless)

    print(f"Result: {result.to_dict()}")
