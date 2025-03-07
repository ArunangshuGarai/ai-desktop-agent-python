import os
import logging
import asyncio
import re
from pathlib import Path
from typing import Dict, List, Any, Union, Optional
import time
from playwright.async_api import async_playwright

class WebService:
    """Service for web automation and browser interactions."""
    
    def __init__(self):
        """Initialize the WebService."""
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)
        
        # Initialize Playwright variables
        self.playwright = None
        self.browser = None
        self.page = None
        
        # Set up screenshots directory
        self.screenshots_dir = Path('screenshots')
        self.screenshots_dir.mkdir(exist_ok=True)
    
    async def start_browser(self) -> Dict[str, Any]:
        """
        Start or connect to a browser instance.
        
        Returns:
            Dictionary with success status or error.
        """
        try:
            if self.browser:
                return {'success': True, 'message': 'Browser already running'}
            
            self.playwright = await async_playwright().start()
            self.browser = await self.playwright.chromium.launch(
                headless=False,
                slow_mo=50  # Slow down operations for visibility
            )
            
            self.page = await self.browser.new_page()
            await self.page.set_viewport_size({'width': 1280, 'height': 800})
            
            self.logger.info('Browser started successfully')
            return {'success': True}
        except Exception as error:
            self.logger.error(f'Error starting browser: {str(error)}')
            return {'success': False, 'error': str(error)}
    
    async def navigate_to_url(self, url: str) -> Dict[str, Any]:
        """
        Navigate to a URL.
        
        Args:
            url: URL to navigate to.
            
        Returns:
            Dictionary with success status or error.
        """
        try:
            if not self.browser or not self.page:
                await self.start_browser()
            
            # Ensure URL has protocol
            if not url.startswith('http://') and not url.startswith('https://'):
                url = 'https://' + url
            
            await self.page.goto(url, wait_until='domcontentloaded')
            title = await self.page.title()
            
            # Take a screenshot
            timestamp = int(time.time() * 1000)
            screenshot_path = self.screenshots_dir / f'nav_{timestamp}.png'
            await self.page.screenshot(path=screenshot_path)
            
            self.logger.info(f'Navigated to {url}, page title: {title}')
            
            return {
                'success': True,
                'title': title,
                'url': self.page.url,
                'screenshot': str(screenshot_path)
            }
        except Exception as error:
            self.logger.error(f'Error navigating to URL: {str(error)}')
            return {'success': False, 'error': str(error)}
    
    async def navigate_to_website(self, url: str) -> Dict[str, Any]:
        """
        Enhanced navigation with verification.
        
        Args:
            url: URL to navigate to.
            
        Returns:
            Dictionary with success status or error.
        """
        try:
            # Import services dynamically to avoid circular imports
            from services.gui_automation_service import gui_automation_service
            from services.vision_service import vision_service
            
            # Launch browser
            await gui_automation_service.execute_command(f'start chrome {url}')
            
            # Wait for page to load
            loaded = False
            attempts = 0
            
            while not loaded and attempts < 5:
                await asyncio.sleep(2)
                screenshot = await vision_service.capture_active_window()
                analysis = await vision_service.analyze_screen_with_ai(f'Checking if {url} is loaded')
                
                loaded = analysis.get('analysis', {}).get('pageLoaded', False)
                attempts += 1
            
            return {'success': loaded}
        except Exception as error:
            self.logger.error(f'Error navigating to website: {str(error)}')
            return {'success': False, 'error': str(error)}
    
    async def interact_with_element(self, selector: str, action: str, value: str = '') -> Dict[str, Any]:
        """
        Interact with a page element.
        
        Args:
            selector: CSS selector of the element to interact with.
            action: Action to perform (click, type, select, etc.).
            value: Value to use for the interaction (if applicable).
            
        Returns:
            Dictionary with success status or error.
        """
        try:
            if not self.browser or not self.page:
                return {'success': False, 'error': 'Browser not started'}
            
            # Take screenshot before action to debug
            timestamp = int(time.time() * 1000)
            before_screenshot_path = self.screenshots_dir / f'before_action_{timestamp}.png'
            await self.page.screenshot(path=before_screenshot_path)
            
            self.logger.info(f'Looking for element: {selector}')
            
            # Try different wait strategies with longer timeout
            try:
                await self.page.wait_for_selector(selector, state='visible', timeout=10000)
            except Exception as wait_error:
                self.logger.info(f'Element not found with standard wait. Checking page content...')
                
                # Check for Google consent page and handle it
                page_content = await self.page.content()
                if 'consent.google.com' in page_content:
                    self.logger.info('Detected Google consent page, attempting to accept...')
                    try:
                        # Try various consent buttons (these selectors may need updating)
                        consent_buttons = [
                            'button[id="L2AGLb"]',  # "I agree" button
                            'button[aria-label="Accept all"]',
                            'button:has-text("Accept all")',
                            'button:has-text("I agree")'
                        ]
                        
                        for button_selector in consent_buttons:
                            button_visible = await self.page.is_visible(button_selector)
                            if button_visible:
                                await self.page.click(button_selector)
                                self.logger.info(f'Clicked consent button: {button_selector}')
                                # Wait for navigation after consent
                                await self.page.wait_for_load_state('domcontentloaded')
                                break
                        
                        # Try again to find the original selector
                        await self.page.wait_for_selector(selector, state='visible', timeout=10000)
                    except Exception as consent_error:
                        self.logger.info(f'Failed to handle consent page: {str(consent_error)}')
                
                # For Google search specifically
                if selector == 'input[name="q"]' and 'Google' in await self.page.title():
                    self.logger.info('Trying alternative Google search selectors...')
                    # Try alternative selectors for Google search
                    alternatives = [
                        'input[title="Search"]',
                        'input[type="text"]',
                        'textarea[name="q"]',  # Google sometimes uses a textarea instead of input
                        'textarea[title="Search"]',
                        '.gLFyf',  # Google's search class
                        '[aria-label="Search"]'
                    ]
                    
                    for alt in alternatives:
                        self.logger.info(f'Trying alternative selector: {alt}')
                        if await self.page.is_visible(alt):
                            self.logger.info(f'Found alternative selector: {alt}')
                            selector = alt  # Use this selector instead
                            break
            
            # Log page title and URL for debugging
            self.logger.info(f'Current page: "{await self.page.title()}" at {self.page.url}')
            
            result = None
            if action == 'click':
                await self.page.click(selector)
                result = {'success': True, 'action': 'click', 'selector': selector}
            elif action == 'type':
                await self.page.fill(selector, value)
                result = {'success': True, 'action': 'type', 'selector': selector, 'value': value}
            elif action == 'select':
                await self.page.select_option(selector, value)
                result = {'success': True, 'action': 'select', 'selector': selector, 'value': value}
            elif action == 'check':
                await self.page.check(selector)
                result = {'success': True, 'action': 'check', 'selector': selector}
            elif action == 'uncheck':
                await self.page.uncheck(selector)
                result = {'success': True, 'action': 'uncheck', 'selector': selector}
            elif action == 'getText':
                text = await self.page.text_content(selector)
                result = {'success': True, 'action': 'getText', 'selector': selector, 'text': text}
            else:
                return {'success': False, 'error': f'Unsupported action: {action}'}
            
            # Take screenshot after action
            after_screenshot_path = self.screenshots_dir / f'action_{timestamp}.png'
            await self.page.screenshot(path=after_screenshot_path)
            result['screenshot'] = str(after_screenshot_path)
            
            return result
        except Exception as error:
            self.logger.error(f'Error interacting with element {selector}: {str(error)}')
            
            # Take error screenshot
            try:
                error_screenshot_path = self.screenshots_dir / f'error_{int(time.time() * 1000)}.png'
                await self.page.screenshot(path=error_screenshot_path)
                self.logger.info(f'Error screenshot saved to: {error_screenshot_path}')
            except Exception as screenshot_error:
                self.logger.error(f'Failed to take error screenshot: {str(screenshot_error)}')
            
            return {'success': False, 'error': str(error)}
    
    async def extract_data(self, selector: Optional[str] = None) -> Dict[str, Any]:
        """
        Extract data from the page.
        
        Args:
            selector: Optional CSS selector to extract specific element(s).
            
        Returns:
            Dictionary with extracted data or error.
        """
        try:
            if not self.browser or not self.page:
                return {'success': False, 'error': 'Browser not started'}
            
            data = None
            if selector:
                await self.page.wait_for_selector(selector, state='visible', timeout=5000)
                data = await self.page.text_content(selector)
            else:
                # Extract page title and URL if no selector provided
                data = {
                    'title': await self.page.title(),
                    'url': self.page.url,
                    'content': await self.page.content()
                }
            
            return {'success': True, 'data': data}
        except Exception as error:
            self.logger.error(f'Error extracting data: {str(error)}')
            return {'success': False, 'error': str(error)}
    
    async def take_screenshot(self, filename: Optional[str] = None) -> Dict[str, Any]:
        """
        Take a screenshot of the current page.
        
        Args:
            filename: Optional filename for the screenshot.
            
        Returns:
            Dictionary with success status, path to screenshot or error.
        """
        try:
            if not self.browser or not self.page:
                return {'success': False, 'error': 'Browser not started'}
            
            if not filename:
                timestamp = int(time.time() * 1000)
                filename = f'screenshot_{timestamp}.png'
            
            screenshot_path = self.screenshots_dir / filename
            await self.page.screenshot(path=screenshot_path, full_page=True)
            
            return {'success': True, 'path': str(screenshot_path)}
        except Exception as error:
            self.logger.error(f'Error taking screenshot: {str(error)}')
            return {'success': False, 'error': str(error)}
    
    async def close_browser(self) -> Dict[str, Any]:
        """
        Close the browser.
        
        Returns:
            Dictionary with success status or error.
        """
        try:
            if self.browser:
                await self.browser.close()
                self.browser = None
                self.page = None
                
                if self.playwright:
                    await self.playwright.stop()
                    self.playwright = None
                
                return {'success': True, 'message': 'Browser closed'}
            
            return {'success': False, 'message': 'No browser instance to close'}
        except Exception as error:
            self.logger.error(f'Error closing browser: {str(error)}')
            return {'success': False, 'error': str(error)}

# Export singleton instance
web_service = WebService()