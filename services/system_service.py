import os
import platform
import subprocess
import logging
import asyncio
from typing import Dict, List, Any, Union, Optional
import pyautogui
import psutil
import re
import time

class SystemService:
    """Service for system-level operations including keyboard, mouse and system operations."""
    
    def __init__(self):
        """Initialize the SystemService."""
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)
        
        # Configure platform-specific settings
        self.is_windows = platform.system() == 'Windows'
        
        # Configure PyAutoGUI for safety
        pyautogui.FAILSAFE = True
        
        # List of potentially dangerous commands to reject
        self.unsafe_patterns = [
            r'rm\s+-rf', 'format', 'mkfs',
            r'dd\s+if=', 'wget', 'curl',
            ';', '&&', '\\|\\|', '`', '\\$\\(',
            '>', '>>', '\\|', 'sudo', 'su '
        ]
    
    def is_unsafe_command(self, command: str) -> bool:
        """
        Check if a command is potentially unsafe.
        
        Args:
            command: The command to check.
            
        Returns:
            True if the command is potentially unsafe, False otherwise.
        """
        if not command:
            return False
        
        # Allow specific safe PowerShell commands
        if "Add-Type" in command and "user32.dll" in command and "SetForegroundWindow" in command:
            # This is our window activation code, which is safe
            return False
            
        for pattern in self.unsafe_patterns:
            if re.search(pattern, command):
                self.logger.warning(f"Potential unsafe command detected: {command}")
                return True
                
        return False
    
    async def execute_command(self, command: str) -> Dict[str, Any]:
        """
        Execute a system command.
        
        Args:
            command: Command to execute.
            
        Returns:
            Dictionary with success status and output or error.
        """
        try:
            if not command:
                return {'success': False, 'error': 'No command provided'}
                
            # Check if command is potentially unsafe
            if self.is_unsafe_command(command):
                return {'success': False, 'error': 'Command execution rejected for security reasons'}
            
            self.logger.info(f"Executing command: {command}")
            
            # Execute command
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            # Wait for the command to complete and get output
            stdout, stderr = await process.communicate()
            
            # Decode output
            stdout_decoded = stdout.decode('utf-8', errors='replace')
            stderr_decoded = stderr.decode('utf-8', errors='replace')
            
            if process.returncode != 0:
                self.logger.error(f"Command failed with exit code {process.returncode}")
                self.logger.error(f"Error output: {stderr_decoded}")
                
                return {
                    'success': False,
                    'command': command,
                    'returncode': process.returncode,
                    'stdout': stdout_decoded,
                    'stderr': stderr_decoded,
                    'error': f"Command failed with exit code {process.returncode}"
                }
            
            return {
                'success': True,
                'command': command,
                'returncode': process.returncode,
                'output': stdout_decoded,
                'stderr': stderr_decoded
            }
        except Exception as error:
            self.logger.error(f"Error executing command: {str(error)}")
            return {'success': False, 'error': str(error)}
    
    async def launch_application(self, path: str, args: List[str] = []) -> Dict[str, Any]:
        """
        Launch an application.
        
        Args:
            path: Path to the application executable.
            args: Command line arguments for the application.
            
        Returns:
            Dictionary with success status or error.
        """
        try:
            if not path:
                return {'success': False, 'error': 'No application path provided'}
            
            self.logger.info(f"Launching application: {path} with args: {args}")
            
            # Create the process
            if self.is_windows:
                # On Windows, we can use the 'start' command
                command = f'start "" "{path}" {" ".join(args)}'
                process = await asyncio.create_subprocess_shell(command)
            else:
                # On other platforms, launch directly
                command = [path] + args
                process = await asyncio.create_subprocess_exec(*command)
            
            # We don't wait for it to complete since it's an application
            return {
                'success': True,
                'path': path,
                'args': args,
                'pid': process.pid
            }
        except Exception as error:
            self.logger.error(f"Error launching application: {str(error)}")
            return {'success': False, 'error': str(error)}
    
    def get_system_info(self) -> Dict[str, Any]:
        """
        Get system information.
        
        Returns:
            Dictionary with system information.
        """
        try:
            info = {
                'platform': platform.system(),
                'platform_version': platform.version(),
                'processor': platform.processor(),
                'hostname': platform.node(),
                'python_version': platform.python_version(),
                'memory': {
                    'total': psutil.virtual_memory().total,
                    'available': psutil.virtual_memory().available,
                    'percent': psutil.virtual_memory().percent
                },
                'disk': {
                    'total': psutil.disk_usage('/').total,
                    'used': psutil.disk_usage('/').used,
                    'free': psutil.disk_usage('/').free,
                    'percent': psutil.disk_usage('/').percent
                },
                'cpu': {
                    'cores': psutil.cpu_count(logical=False),
                    'logical_cores': psutil.cpu_count(logical=True),
                    'percent': psutil.cpu_percent(interval=1)
                }
            }
            
            return {'success': True, 'info': info}
        except Exception as error:
            self.logger.error(f"Error getting system info: {str(error)}")
            return {'success': False, 'error': str(error)}
    
    async def get_running_processes(self) -> Dict[str, Any]:
        """
        Get list of running processes.
        
        Returns:
            Dictionary with list of running processes.
        """
        try:
            processes = []
            for proc in psutil.process_iter(['pid', 'name', 'username', 'memory_info']):
                try:
                    # Get process info
                    proc_info = proc.info
                    processes.append({
                        'pid': proc_info['pid'],
                        'name': proc_info['name'],
                        'username': proc_info['username'],
                        'memory': proc_info['memory_info'].rss if proc_info['memory_info'] else 0
                    })
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    pass
            
            return {'success': True, 'processes': processes}
        except Exception as error:
            self.logger.error(f"Error getting running processes: {str(error)}")
            return {'success': False, 'error': str(error)}
    
    async def simulate_input(self, input_sequence: str) -> Dict[str, Any]:
        """
        Simulate keyboard input.
        
        Args:
            input_sequence: Sequence of keys to simulate.
            
        Returns:
            Dictionary with success status or error.
        """
        try:
            if not input_sequence:
                return {'success': False, 'error': 'No input sequence provided'}
            
            self.logger.info(f"Simulating input: {input_sequence}")
            
            # Write the input sequence using PyAutoGUI
            pyautogui.write(input_sequence)
            
            return {'success': True, 'input': input_sequence}
        except Exception as error:
            self.logger.error(f"Error simulating input: {str(error)}")
            return {'success': False, 'error': str(error)}
    
    async def press_key(self, key: str) -> Dict[str, Any]:
        """
        Press a specific key.
        
        Args:
            key: Key to press.
            
        Returns:
            Dictionary with success status or error.
        """
        try:
            if not key:
                return {'success': False, 'error': 'No key specified'}
            
            self.logger.info(f"Pressing key: {key}")
            
            # Press the key using PyAutoGUI
            pyautogui.press(key)
            
            return {'success': True, 'key': key}
        except Exception as error:
            self.logger.error(f"Error pressing key: {str(error)}")
            return {'success': False, 'error': str(error)}
    
    async def press_keys(self, keys: List[str]) -> Dict[str, Any]:
        """
        Press multiple keys simultaneously (keyboard shortcut).
        
        Args:
            keys: List of keys to press simultaneously.
            
        Returns:
            Dictionary with success status or error.
        """
        try:
            if not keys:
                return {'success': False, 'error': 'No keys specified'}
            
            self.logger.info(f"Pressing keys: {' + '.join(keys)}")
            
            # Press the keys using PyAutoGUI hotkey
            pyautogui.hotkey(*keys)
            
            return {'success': True, 'keys': keys}
        except Exception as error:
            self.logger.error(f"Error pressing keys: {str(error)}")
            return {'success': False, 'error': str(error)}
    
    async def mouse_move(self, x: int, y: int) -> Dict[str, Any]:
        """
        Move the mouse to specific coordinates.
        
        Args:
            x: X coordinate.
            y: Y coordinate.
            
        Returns:
            Dictionary with success status or error.
        """
        try:
            self.logger.info(f"Moving mouse to: ({x}, {y})")
            
            # Move the mouse using PyAutoGUI with a small duration for smoother movement
            pyautogui.moveTo(x, y, duration=0.5)
            
            # Wait a moment for the UI to respond to mouse hover
            await asyncio.sleep(0.2)
            
            return {'success': True, 'x': x, 'y': y}
        except Exception as error:
            self.logger.error(f"Error moving mouse: {str(error)}")
            return {'success': False, 'error': str(error)}
    
    async def mouse_click(self, x: Optional[int] = None, y: Optional[int] = None, button: str = 'left') -> Dict[str, Any]:
        """
        Click the mouse at the current position or specified coordinates.
        
        Args:
            x: Optional X coordinate. If None, clicks at current position.
            y: Optional Y coordinate. If None, clicks at current position.
            button: Mouse button to click ('left', 'right', 'middle').
            
        Returns:
            Dictionary with success status or error.
        """
        try:
            if x is not None and y is not None:
                self.logger.info(f"Moving and clicking {button} button at: ({x}, {y})")
                
                # First move the mouse to the position
                await self.mouse_move(x, y)
                
                # Then perform the click
                pyautogui.click(button=button)
            else:
                self.logger.info(f"Clicking {button} button at current position")
                
                # Click at the current position
                pyautogui.click(button=button)
            
            # Wait after click to ensure action completes
            await asyncio.sleep(0.5)
            
            # Get the current mouse position
            current_pos = pyautogui.position()
            
            return {
                'success': True,
                'button': button,
                'position': {'x': current_pos.x, 'y': current_pos.y}
            }
        except Exception as error:
            self.logger.error(f"Error clicking mouse: {str(error)}")
            return {'success': False, 'error': str(error)}
    
    async def scroll(self, direction: str, amount: int) -> Dict[str, Any]:
        """
        Scroll the mouse wheel.
        
        Args:
            direction: Direction to scroll ('up' or 'down').
            amount: Amount to scroll.
            
        Returns:
            Dictionary with success status or error.
        """
        try:
            if direction not in ['up', 'down']:
                return {'success': False, 'error': 'Invalid scroll direction. Use "up" or "down".'}
            
            self.logger.info(f"Scrolling {direction} by {amount}")
            
            # Calculate the scroll amount (positive for up, negative for down)
            scroll_amount = amount if direction == 'up' else -amount
            
            # Scroll using PyAutoGUI
            pyautogui.scroll(scroll_amount)
            
            return {'success': True, 'direction': direction, 'amount': amount}
        except Exception as error:
            self.logger.error(f"Error scrolling: {str(error)}")
            return {'success': False, 'error': str(error)}
    
    def get_screen_info(self) -> Dict[str, Any]:
        """
        Get information about the system screens.
        
        Returns:
            Dictionary with screen information.
        """
        try:
            # Get screen size using PyAutoGUI
            screen_size = pyautogui.size()
            
            # Get mouse position
            mouse_pos = pyautogui.position()
            
            return {
                'success': True,
                'screens': [
                    {
                        'id': 'primary',
                        'width': screen_size.width,
                        'height': screen_size.height
                    }
                ],
                'mouse_position': {'x': mouse_pos.x, 'y': mouse_pos.y}
            }
        except Exception as error:
            self.logger.error(f"Error getting screen info: {str(error)}")
            return {'success': False, 'error': str(error)}
            
    async def find_and_activate_window(self, window_title: str) -> Dict[str, Any]:
        """
        Find and activate a window by title.
        
        Args:
            window_title: Part of the window title to search for.
            
        Returns:
            Dictionary with success status or error.
        """
        try:
            self.logger.info(f"Finding and activating window: {window_title}")
            
            if self.is_windows:
                # PowerShell script to find and activate window
                ps_command = f"""
                Add-Type @"
                using System;
                using System.Runtime.InteropServices;
                public class Win32 {{
                    [DllImport("user32.dll")]
                    [return: MarshalAs(UnmanagedType.Bool)]
                    public static extern bool SetForegroundWindow(IntPtr hWnd);
                    
                    [DllImport("user32.dll")]
                    public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);
                }}
"@
                
                $windows = Get-Process | Where-Object {{($_.MainWindowTitle -like "*{window_title}*") -and ($_.MainWindowHandle -ne 0)}}
                if ($windows) {{
                    $handle = $windows.MainWindowHandle
                    [Win32]::ShowWindow($handle, 9) # SW_RESTORE = 9
                    [Win32]::SetForegroundWindow($handle)
                    Write-Output "Window activated: $($windows.MainWindowTitle)"
                    exit 0
                }} else {{
                    Write-Output "Window not found with title containing: {window_title}"
                    exit 1
                }}
                """
                
                # Execute PowerShell script
                result = await self.execute_command(f'powershell -Command "{ps_command}"')
                
                # Wait for window to be properly activated
                await asyncio.sleep(1)
                
                return result
            else:
                # For non-Windows platforms, use a simple method
                return {'success': False, 'error': 'Window activation is currently only supported on Windows'}
                
        except Exception as error:
            self.logger.error(f"Error finding and activating window: {str(error)}")
            return {'success': False, 'error': str(error)}
    
    async def interactWithBrowser(self, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Perform browser-specific interactions.
        
        Args:
            action: Type of browser action to perform.
            params: Parameters for the action.
            
        Returns:
            Dictionary with success status or error.
        """
        try:
            self.logger.info(f"Performing browser interaction: {action}")
            
            if action == 'search':
                # Get search text from params
                search_text = params.get('searchText', '')
                if not search_text:
                    return {'success': False, 'error': 'No search text provided'}
                
                # First focus the browser window
                await self.find_and_activate_window('Chrome')
                await asyncio.sleep(1)
                
                # Get screen dimensions
                screen_info = self.get_screen_info()
                if not screen_info.get('success', False):
                    return {'success': False, 'error': 'Failed to get screen info'}
                
                # Click in address bar (approximate position in the top third of the screen)
                screen_width = screen_info['screens'][0]['width']
                await self.mouse_click(int(screen_width * 0.5), 50)
                await asyncio.sleep(0.5)
                
                # Clear existing text with Ctrl+A and Delete
                await self.press_keys(['ctrl', 'a'])
                await asyncio.sleep(0.2)
                await self.press_key('delete')
                await asyncio.sleep(0.2)
                
                # Type the search text
                await self.simulate_input(search_text)
                await asyncio.sleep(0.5)
                
                # Press Enter to search
                await self.press_key('enter')
                
                return {'success': True, 'action': 'browser-search', 'text': search_text}
            elif action == 'navigate':
                # Get URL from params
                url = params.get('url', '')
                if not url:
                    return {'success': False, 'error': 'No URL provided'}
                
                # Launch Chrome with the URL
                command = f'start chrome {url}'
                result = await self.execute_command(command)
                
                # Wait for browser to load
                await asyncio.sleep(2)
                
                return {'success': True, 'action': 'browser-navigate', 'url': url}
            
            elif action == 'screenshot':
                # Import vision service for taking screenshots
                from services.vision_service import VisionService
                vision_service = VisionService()
                
                # Get filename from params or generate one
                filename = params.get('filename', f'screenshot_{int(time.time())}.png')
                
                # Take screenshot
                result = await vision_service.take_screenshot(filename)
                
                # Make sure to emit an event for the UI
                self.emit('screenshot-taken', {'path': result.get('path', '')})
                
                return result
            
            else:
                return {'success': False, 'error': f'Unsupported browser action: {action}'}
                
        except Exception as error:
            self.logger.error(f"Error in browser interaction: {str(error)}")
            return {'success': False, 'error': str(error)}
    async def execute_system_action(self, action: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a system-related action.
        
        Args:
            action: The action to execute.
            
        Returns:
            Dictionary with success status and output or error.
        """
        # Import the service dynamically to avoid circular imports
        
        action_type = action.get('action', '')
        params = action.get('params', {})
        
        if action_type == 'simulate_input':
            return await self.simulate_input(params.get('input_sequence', ''))
        elif action_type == 'getInfo':
            return self.get_system_info()
        elif action_type in ['execute', 'execute_system_command', 'execute system command']:
            return await self.execute_command(params.get('command', ''))
        elif action_type == 'launch':
            return await self.launch_application(
                params.get('path', ''), 
                params.get('args', [])
            )
        elif action_type == 'getProcesses':
            return await self.get_running_processes()
        elif action_type == 'interactWithBrowser':
            return await self.interactWithBrowser(
                params.get('action', ''),
                params
            )
        elif action_type == 'screenshot' or action_type == 'take_screenshot':
            # Handle screenshot action directly in system service
            try:
                import pyautogui
                import time
                import os
                from pathlib import Path
                
                # Create screenshots directory if it doesn't exist
                screenshots_dir = Path('screenshots')
                screenshots_dir.mkdir(exist_ok=True)
                
                # Generate filename if not provided
                filename = params.get('filename', f'screenshot_{int(time.time())}.png')
                
                # Ensure path is absolute
                if not os.path.isabs(filename):
                    filepath = screenshots_dir / filename
                else:
                    filepath = Path(filename)
                    
                # Take the screenshot
                self.logger.info(f"Taking screenshot, saving to: {filepath}")
                screenshot = pyautogui.screenshot()
                screenshot.save(str(filepath))
                
                return {
                    'success': True,
                    'action': 'screenshot',
                    'path': str(filepath)
                }
            except Exception as error:
                self.logger.error(f"Error taking screenshot: {str(error)}")
                return {'success': False, 'error': str(error)}
    
    async def sleep(self, milliseconds: int) -> None:
        """
        Sleep for the specified number of milliseconds.
        
        Args:
            milliseconds: Number of milliseconds to sleep.
        """
        await asyncio.sleep(milliseconds / 1000)

# Export singleton instance
system_service = SystemService()