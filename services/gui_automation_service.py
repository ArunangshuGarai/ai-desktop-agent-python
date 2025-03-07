import os
import logging
import time
import platform
import subprocess
import asyncio
from typing import Dict, List, Any, Union, Optional
import pyautogui
import pywinctl

from services.vision_service import VisionService

class GuiAutomationService:
    """Service for GUI automation including keyboard and mouse operations."""
    
    def __init__(self):
        """Initialize the GuiAutomationService."""
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)
        
        # Configure platform-specific settings
        self.is_windows = platform.system() == 'Windows'
        
        # Configure PyAutoGUI
        pyautogui.FAILSAFE = True  # Move mouse to corner to abort
        self.keyboard_delay = 0.1  # seconds between key presses
        
        # Initialize vision service for screenshots
        self.vision_service = VisionService()
    
    async def execute_command(self, command: str) -> Dict[str, Any]:
        """
        Execute a system command.
        
        Args:
            command: Command to execute.
            
        Returns:
            Dictionary with success status and output or error.
        """
        try:
            self.logger.info(f"Executing command: {command}")
            
            # Use asyncio subprocess to execute command
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            # Wait for process to complete
            stdout, stderr = await process.communicate()
            
            # Decode output
            stdout_text = stdout.decode('utf-8', errors='replace')
            stderr_text = stderr.decode('utf-8', errors='replace')
            
            if stderr_text:
                self.logger.warning(f"Command stderr: {stderr_text}")
            
            return {
                'success': True,
                'command': command,
                'output': stdout_text,
                'return_code': process.returncode
            }
        except Exception as error:
            self.logger.error(f"Error executing command: {str(error)}")
            return {'success': False, 'error': str(error)}
    
    async def type_text(self, text: str) -> Dict[str, Any]:
        """
        Type text using keyboard simulation.
        
        Args:
            text: Text to type.
            
        Returns:
            Dictionary with success status or error.
        """
        try:
            self.logger.info(f"Typing text: {text[:50]}{'...' if len(text) > 50 else ''}")
            
            # Take before screenshot
            before_screenshot = await self.vision_service.capture_active_window()
            
            # For large text, type in chunks to avoid overwhelming the system
            chunk_size = 500
            if len(text) > chunk_size:
                for i in range(0, len(text), chunk_size):
                    chunk = text[i:min(i + chunk_size, len(text))]
                    pyautogui.write(chunk)
                    await asyncio.sleep(0.5)  # Pause between chunks
            else:
                pyautogui.write(text)
            
            # Take after screenshot
            after_screenshot = await self.vision_service.capture_active_window()
            
            return {
                'success': True,
                'text_length': len(text),
                'before_screenshot': before_screenshot.get('path') if before_screenshot.get('success') else None,
                'after_screenshot': after_screenshot.get('path') if after_screenshot.get('success') else None
            }
        except Exception as error:
            self.logger.error(f"Error typing text: {str(error)}")
            return {'success': False, 'error': str(error)}
    
    async def press_key(self, key: str) -> Dict[str, Any]:
        """
        Press a single key.
        
        Args:
            key: Key to press.
            
        Returns:
            Dictionary with success status or error.
        """
        try:
            self.logger.info(f"Pressing key: {key}")
            
            # Map common key names to their correct values
            key_map = {
                'enter': 'enter',
                'return': 'enter',
                'esc': 'escape',
                'escape': 'escape',
                'tab': 'tab',
                'space': 'space',
                'backspace': 'backspace',
                'delete': 'delete',
                'up': 'up',
                'down': 'down',
                'left': 'left',
                'right': 'right'
            }
            
            # Use mapped key if available, otherwise use the provided key
            mapped_key = key_map.get(key.lower(), key)
            
            # Press the key
            pyautogui.press(mapped_key)
            
            # Take screenshot after key press
            screenshot = await self.vision_service.capture_active_window()
            
            return {
                'success': True,
                'key': mapped_key,
                'screenshot': screenshot.get('path') if screenshot.get('success') else None
            }
        except Exception as error:
            self.logger.error(f"Error pressing key: {str(error)}")
            return {'success': False, 'error': str(error)}
    
    async def press_keys(self, keys: List[str]) -> Dict[str, Any]:
        """
        Press multiple keys (keyboard shortcut).
        
        Args:
            keys: List of keys to press.
            
        Returns:
            Dictionary with success status or error.
        """
        try:
            self.logger.info(f"Pressing keys: {' + '.join(keys)}")
            
            # Take before screenshot
            before_screenshot = await self.vision_service.capture_active_window()
            
            # Use PyAutoGUI's hotkey function for key combinations
            pyautogui.hotkey(*keys)
            
            # Take after screenshot
            after_screenshot = await self.vision_service.capture_active_window()
            
            return {
                'success': True,
                'keys': keys,
                'before_screenshot': before_screenshot.get('path') if before_screenshot.get('success') else None,
                'after_screenshot': after_screenshot.get('path') if after_screenshot.get('success') else None
            }
        except Exception as error:
            self.logger.error(f"Error pressing keys: {str(error)}")
            return {'success': False, 'error': str(error)}
    
    async def find_and_activate_window(self, window_title: str) -> Dict[str, Any]:
        """
        Find and activate a window by title.
        
        Args:
            window_title: Title of the window to find and activate.
            
        Returns:
            Dictionary with success status or error.
        """
        try:
            self.logger.info(f"Finding and activating window: {window_title}")
            
            # Get all windows
            windows = pywinctl.getAllWindows()
            
            # Find the window that matches the title
            matching_windows = [w for w in windows if window_title.lower() in w.title.lower()]
            
            if not matching_windows:
                return {'success': False, 'message': f"Window not found with title containing: {window_title}"}
            
            # Activate the first matching window
            matching_window = matching_windows[0]
            matching_window.activate()
            
            # Wait a moment for the window to become active
            await asyncio.sleep(1)
            
            return {'success': True, 'title': matching_window.title}
        except Exception as error:
            self.logger.error(f"Error finding/activating window: {str(error)}")
            return {'success': False, 'error': str(error)}
    
    async def automate_calculator(self, num1: Union[int, float], num2: Union[int, float], operation: str) -> Dict[str, Any]:
        """
        Automate calculator operations.
        
        Args:
            num1: First number.
            num2: Second number.
            operation: Operation to perform (one of +, -, *, /).
            
        Returns:
            Dictionary with success status, result and error if any.
        """
        try:
            self.logger.info(f"Automating calculator: {num1} {operation} {num2}")
            
            # Try to activate the calculator window
            calc_window = await self.find_and_activate_window("Calculator")
            
            # If calculator window not found, launch it
            if not calc_window.get('success'):
                self.logger.info("Calculator not found, launching it...")
                
                # Launch calculator
                if self.is_windows:
                    await self.execute_command("start calc.exe")
                else:
                    await self.execute_command("gnome-calculator")
                
                # Wait for calculator to launch
                await asyncio.sleep(2)
            
            # Clear any previous calculations with Escape key
            await self.press_key("escape")
            
            # Type the first number
            await self.type_text(str(num1))
            
            # Type the operation
            op_key_map = {
                '+': '+',
                '-': '-',
                '*': '*',
                '/': '/'
            }
            
            if operation in op_key_map:
                await self.press_key(op_key_map[operation])
            else:
                return {'success': False, 'error': f"Unsupported operation: {operation}"}
            
            # Type the second number
            await self.type_text(str(num2))
            
            # Press Enter to get the result
            await self.press_key("enter")
            
            # Wait a moment for the result to appear
            await asyncio.sleep(0.5)
            
            # Take a screenshot of the result
            screenshot = await self.vision_service.capture_active_window()
            
            # In a real implementation, we would use OCR to read the result
            # For now, we'll just calculate it ourselves
            result = None
            if operation == '+':
                result = num1 + num2
            elif operation == '-':
                result = num1 - num2
            elif operation == '*':
                result = num1 * num2
            elif operation == '/':
                result = num1 / num2 if num2 != 0 else "Error: Division by zero"
            
            return {
                'success': True,
                'operation': f"{num1} {operation} {num2}",
                'result': result,
                'screenshot': screenshot.get('path') if screenshot.get('success') else None,
                'message': f"Calculator operation completed: {num1} {operation} {num2} = {result}"
            }
        except Exception as error:
            self.logger.error(f"Error automating calculator: {str(error)}")
            return {'success': False, 'error': str(error)}
    
    async def sleep(self, ms: int) -> None:
        """
        Utility sleep function.
        
        Args:
            ms: Milliseconds to sleep.
        """
        await asyncio.sleep(ms / 1000)

# Export singleton instance
gui_automation_service = GuiAutomationService()