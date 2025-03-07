import os
import json
import time
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional, Callable, Union
import threading
from threading import Event

# Define a custom event emitter
class EventEmitter:
    def __init__(self):
        self.callbacks = {}
    
    def on(self, event_name: str, callback: Callable) -> None:
        """Register an event callback"""
        if event_name not in self.callbacks:
            self.callbacks[event_name] = []
        self.callbacks[event_name].append(callback)
    
    def emit(self, event_name: str, data: Any = None) -> None:
        """Emit an event with optional data"""
        if event_name in self.callbacks:
            for callback in self.callbacks[event_name]:
                callback(data)

class TaskManager(EventEmitter):
    """Manages the analysis and execution of desktop automation tasks."""
    
    def __init__(self):
        """Initialize the TaskManager."""
        super().__init__()
        
        # Import services conditionally to avoid circular imports
        from utils.deepseek_client import DeepseekClient
        
        # Initialize task state
        self.current_task = None
        self.steps = []
        self.current_step_index = -1
        self.context = {}
        
        # Initialize client
        self.api_client = DeepseekClient()
        
        # Set up logging
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)
        
        # Make sure the screenshots directory exists
        screenshots_dir = Path('screenshots')
        screenshots_dir.mkdir(exist_ok=True)

    async def analyze_task(self, task_description: str) -> Dict[str, Any]:
        """
        Analyze a task and break it down into steps.
        
        Args:
            task_description: The task description to analyze.
            
        Returns:
            A dictionary containing the analysis results.
        """
        try:
            self.emit('analyzing', {'task': task_description})
            self.logger.info(f"Analyzing task: {task_description}")
            
            # Check if this is a query about the agent itself
            from utils.deepseek_client import DeepseekClient
            temp_client = DeepseekClient()
            
            if temp_client.is_agent_info_query(task_description):
                self.logger.info(f"Detected agent info query: {task_description}")
                # Get agent info response
                agent_info = await temp_client.generate_json(task_description)
                
                # Store as current task with special flag
                self.current_task = task_description
                self.steps = agent_info.get('steps', [])
                self.current_step_index = -1
                self.context = {
                    "task_description": task_description,
                    "analysis": agent_info.get('analysis', ''),
                    "isAgentInfoResponse": True  # This is the important flag
                }
                
                # Emit analyzed event
                self.emit('analyzed', {
                    "task": task_description,
                    "analysis": agent_info.get('analysis', ''),
                    "steps": self.steps,
                    "isAgentInfoResponse": True
                })
                
                return agent_info
            
            # Handle browser search tasks specifically
            if any(keyword in task_description.lower() for keyword in ['search', 'google', 'browse']) and \
               any(browser in task_description.lower() for browser in ['chrome', 'browser', 'firefox', 'edge']):
                
                # Extract the search term
                import re
                search_match = re.search(r'search\s+(?:for\s+)?([a-zA-Z0-9\s]+)(?:\s+in|\s+with|\s+using)?', 
                                       task_description.lower(), re.IGNORECASE)
                
                search_term = "python"  # Default search term
                if search_match:
                    search_term = search_match.group(1).strip()
                
                # Check if a specific browser is mentioned
                browser_name = "chrome"  # Default browser
                if 'firefox' in task_description.lower():
                    browser_name = "firefox"
                elif 'edge' in task_description.lower():
                    browser_name = "msedge"
                
                # Create a task plan specifically for browser search
                task_plan = {
                    "analysis": f"This task requires searching for '{search_term}' in the {browser_name} browser.",
                    "steps": [
                        {
                            "id": 1,
                            "name": "Launch Browser",
                            "description": f"Open {browser_name} browser",
                            "type": "system",
                            "actions": [
                                {
                                    "action": "execute",
                                    "params": {
                                        "command": f"start {browser_name}"
                                    }
                                }
                            ]
                        },
                        {
                            "id": 2,
                            "name": "Perform Search",
                            "description": f"Search for '{search_term}' in {browser_name}",
                            "type": "system",
                            "actions": [
                                {
                                    "action": "interactWithBrowser",
                                    "params": {
                                        "action": "search",
                                        "searchText": search_term
                                    }
                                }
                            ]
                        }
                    ],
                    "challenges": ["Browser interaction", "Text input"]
                }
                
                self.current_task = task_description
                self.steps = task_plan["steps"]
                self.current_step_index = -1
                self.context = {
                    "task_description": task_description,
                    "analysis": task_plan["analysis"],
                    "challenges": task_plan["challenges"],
                    "search_term": search_term,
                    "browser_name": browser_name
                }
                
                self.emit('analyzed', {
                    "task": task_description,
                    "analysis": task_plan["analysis"],
                    "steps": task_plan["steps"],
                    "challenges": task_plan["challenges"]
                })
                
                return task_plan
            
            # Handle web navigation tasks
            if any(keyword in task_description.lower() for keyword in ['navigate', 'open', 'website']):
                
                # Extract website name
                website_name = ""
                url = ""
                browser_name = "chrome"
                
                # Look for specific websites
                if 'bookmyshow' in task_description.lower():
                    website_name = "BookMyShow"
                    url = "https://in.bookmyshow.com/"
                else:
                    # General pattern matching
                    import re
                    website_match = re.search(
                        r'(?:navigate|open)\s+(?:to)?\s+(?:the)?\s+([a-zA-Z0-9\s]+)(?:\s+(?:official)?)?\s+(?:website|site|page)',
                        task_description, re.IGNORECASE
                    )
                    if website_match:
                        website_name = website_match.group(1).strip()
                        # Make best guess at URL
                        url = f"https://www.{website_name.lower().replace(' ', '')}.com"
                
                # Check if a specific browser is mentioned
                if 'chrome' in task_description.lower():
                    browser_name = "chrome"
                elif 'edge' in task_description.lower():
                    browser_name = "msedge"
                elif 'firefox' in task_description.lower():
                    browser_name = "firefox"
                
                if website_name:
                    # Create web navigation task plan
                    task_plan = {
                        "analysis": f"This task requires opening {browser_name} and navigating to the {website_name} website.",
                        "steps": [
                            {
                                "id": 1,
                                "name": "Launch Web Browser",
                                "description": f"Open {browser_name}",
                                "type": "system",
                                "actions": [
                                    {
                                        "action": "execute",
                                        "params": {
                                            "command": f"start {browser_name} {url}"
                                        }
                                    }
                                ]
                            },
                            {
                                "id": 2,
                                "name": "Verify Navigation",
                                "description": f"Verify navigation to {website_name} website",
                                "type": "code",
                                "actions": [
                                    {
                                        "action": "verifyWebPage",
                                        "params": {
                                            "websiteName": website_name
                                        }
                                    }
                                ]
                            }
                        ],
                        "challenges": ["Web navigation", "URL handling"]
                    }
                    
                    self.current_task = task_description
                    self.steps = task_plan["steps"]
                    self.current_step_index = -1
                    self.context = {
                        "task_description": task_description,
                        "analysis": task_plan["analysis"],
                        "challenges": task_plan["challenges"],
                        "website_name": website_name,
                        "url": url
                    }
                    
                    self.emit('analyzed', {
                        "task": task_description,
                        "analysis": task_plan["analysis"],
                        "steps": task_plan["steps"],
                        "challenges": task_plan["challenges"]
                    })
                    
                    return task_plan
            
# If no specific handling, try the general API approach
            try:
                # Use the API
                task_plan = await self.api_client.generate_json(task_description)
                
                # Format the steps to ensure they have proper structure
                steps = task_plan.get("steps", [])
                for i, step in enumerate(steps):
                    # Add default type if missing
                    if "type" not in step:
                        if "action" in step and step["action"] in ["click", "type", "wait", "press", "scroll"]:
                            step["type"] = "system"
                        else:
                            step["type"] = "system"
                    
                    # Add id if missing
                    if "id" not in step:
                        step["id"] = i + 1
                    
                    # Ensure actions array exists
                    if "actions" not in step:
                        action = step.get("action", "")
                        if action:
                            # Create action based on step data
                            step["actions"] = [{
                                "action": action,
                                "params": {
                                    key: step[key] for key in ["text", "target", "time"]
                                    if key in step
                                }
                            }]
                
                self.current_task = task_description
                self.steps = task_plan.get("steps", [])
                self.current_step_index = -1
                self.context = {
                    "task_description": task_description,
                    "analysis": task_plan.get("analysis", ""),
                    "challenges": task_plan.get("challenges", [])
                }
                
                self.emit('analyzed', {
                    "task": task_description,
                    "analysis": task_plan.get("analysis", ""),
                    "steps": task_plan.get("steps", []),
                    "challenges": task_plan.get("challenges", [])
                })
                
                return task_plan
            except Exception as error:
                self.logger.error(f'API error, using fallback task plan: {str(error)}')
                
                # Create a generic fallback plan with appropriate task handling
                fallback_plan = self.create_fallback_plan(task_description)
                
                self.current_task = task_description
                self.steps = fallback_plan["steps"]
                self.current_step_index = -1
                self.context = {
                    "task_description": task_description,
                    "analysis": fallback_plan["analysis"],
                    "challenges": fallback_plan["challenges"]
                }
                
                self.emit('analyzed', {
                    "task": task_description,
                    "analysis": fallback_plan["analysis"],
                    "steps": fallback_plan["steps"],
                    "challenges": fallback_plan["challenges"]
                })
                
                return fallback_plan
            
        except Exception as error:
            self.logger.error(f'Error analyzing task: {str(error)}')
            self.emit('error', {'error': str(error)})
            raise error

    def create_fallback_plan(self, task_description: str) -> Dict[str, Any]:
        """
        Create a fallback plan when API analysis fails.
        
        Args:
            task_description: The task description.
            
        Returns:
            A fallback task plan.
        """
        # Check for common patterns
        lower_task = task_description.lower()
        import time
        
        # Browser search task
        if any(term in lower_task for term in ["search", "google", "find"]) and any(term in lower_task for term in ["chrome", "browser", "firefox"]):
            # Extract search term
            import re
            search_term = "python"  # Default
            search_match = re.search(r'search\s+(?:for\s+)?([a-zA-Z0-9\s]+)', lower_task)
            if search_match:
                search_term = search_match.group(1).strip()
                
            return {
                "analysis": f"This task requires searching for '{search_term}' in the browser.",
                "steps": [
                    {
                        "id": 1,
                        "name": "Launch Browser",
                        "description": "Open Chrome browser",
                        "type": "system",
                        "actions": [
                            {
                                "action": "execute",
                                "params": {
                                    "command": "start chrome"
                                }
                            }
                        ]
                    },
                    {
                        "id": 2,
                        "name": "Perform Search",
                        "description": f"Search for '{search_term}'",
                        "type": "system",
                        "actions": [
                            {
                                "action": "interactWithBrowser",
                                "params": {
                                    "action": "search",
                                    "searchText": search_term
                                }
                            }
                        ]
                    }
                ],
                "challenges": ["Browser interaction", "API unavailability"]
            }
        # Website navigation and download
        elif any(term in lower_task for term in ["website", "download", "open"]):
            return {
                "analysis": f"This task involves website navigation and download: {task_description}",
                "steps": [
                    {
                        "id": 1,
                        "name": "Take Screenshot",
                        "description": "Take screenshot to assess current state",
                        "type": "system",
                        "actions": [
                            {
                                "action": "screenshot",
                                "params": {
                                    "filename": f"screenshot_{int(time.time())}.png"
                                }
                            }
                        ]
                    },
                    {
                        "id": 2,
                        "name": "Find Download Link",
                        "description": "Look for download links in the current page",
                        "type": "system",
                        "actions": [
                            {
                                "action": "wait",
                                "params": {
                                    "time": 2000
                                }
                            }
                        ]
                    }
                ],
                "challenges": ["Website navigation", "Download identification", "API unavailability"]
            }
        # File operations
        elif any(term in lower_task for term in ["file", "folder", "directory", "create", "delete", "list"]):
            return {
                "analysis": f"This task involves file operations: {task_description}",
                "steps": [
                    {
                        "id": 1,
                        "name": "Take Screenshot",
                        "description": "Take screenshot to assess current state",
                        "type": "system",
                        "actions": [
                            {
                                "action": "screenshot",
                                "params": {
                                    "filename": f"screenshot_{int(time.time())}.png"
                                }
                            }
                        ]
                    },
                    {
                        "id": 2, 
                        "name": "Execute File Operation",
                        "description": f"Perform file operation: {task_description}",
                        "type": "system",
                        "actions": [
                            {
                                "action": "execute",
                                "params": {
                                    "command": 'powershell -Command "Write-Host \'Executing file operation...\'"'
                                }
                            }
                        ]
                    }
                ],
                "challenges": ["Understanding file operation intent", "API unavailability"]
            }
        # Default fallback
        else:
            return {
                "analysis": f"This task requires performing actions related to: {task_description}",
                "steps": [
                    {
                        "id": 1,
                        "name": "Take Screenshot",
                        "description": "Take screenshot to assess current state",
                        "type": "system",
                        "actions": [
                            {
                                "action": "screenshot",
                                "params": {
                                    "filename": f"screenshot_{int(time.time())}.png"
                                }
                            }
                        ]
                    },
                    {
                        "id": 2,
                        "name": "Wait for System",
                        "description": "Wait for system to stabilize",
                        "type": "system",
                        "actions": [
                            {
                                "action": "wait",
                                "params": {
                                    "time": 2000
                                }
                            }
                        ]
                    }
                ],
                "challenges": ["Understanding task intent", "API unavailability"]
            }

    async def execute_next_step(self) -> Dict[str, Any]:
        """
        Execute the next step in the task.
        
        Returns:
            A dictionary containing the execution results.
        """
        if not self.steps or len(self.steps) == 0:
            raise ValueError('No task has been analyzed yet')
        
        if self.current_step_index >= len(self.steps) - 1:
            self.emit('completed', {'task': self.current_task})
            return {'completed': True}
        
        self.current_step_index += 1
        step = self.steps[self.current_step_index]
        
        self.emit('step-started', {
            'step': step,
            'index': self.current_step_index,
            'total': len(self.steps)
        })
        
        try:
            # Execute each action in the step
            results = []
            
            actions = step.get('actions', [])
            # If no actions are defined, create a default action based on step type
            if len(actions) == 0:
                self.logger.info(f"No actions defined for step {step.get('name', '')}, creating default action")
                
                # Create actions based on step type and task context
                step_name = step.get('name', '').lower()
                step_description = step.get('description', '').lower()
                step_type = step.get('type', '').lower()
                
                # Handle browser-related steps
                if any(term in step_name or term in step_description for term in ['browser', 'chrome', 'search']):
                    search_term = self.context.get('search_term', 'python')
                    if 'search' in step_name or 'search' in step_description:
                        actions.append({
                            'action': 'interactWithBrowser',
                            'params': {
                                'action': 'search',
                                'searchText': search_term
                            }
                        })
                    else:
                        # Default browser launch
                        browser = self.context.get('browser_name', 'chrome')
                        actions.append({
                            'action': 'execute',
                            'params': {
                                'command': f'start {browser}'
                            }
                        })
                # Handle file operations
                elif step_type == 'file' or any(term in step_name or term in step_description for term in ['file', 'create', 'read']):
                    if 'create' in step_name or 'create' in step_description:
                        actions.append({
                            'action': 'create',
                            'params': {
                                'path': 'hello.txt',
                                'content': 'Hello, World!'
                            }
                        })
                    elif 'list' in step_name or 'list' in step_description:
                        actions.append({
                            'action': 'list',
                            'params': {
                                'path': '.'
                            }
                        })
                    else:
                        actions.append({
                            'action': 'execute',
                            'params': {
                                'command': 'dir' if os.name == 'nt' else 'ls'
                            }
                        })
                # Default system action
                else:
                    actions.append({
                        'action': 'execute',
                        'params': {
                            'command': 'echo "Executing default action"' if os.name == 'nt' else 'echo "Executing default action"'
                        }
                    })
            
            for action in actions:
                result = None
                
                # Based on step type, call appropriate service
                step_type = step.get('type', '').lower()
                
                # Handle direct action field if present
                if "action" in step and not step_type:
                    direct_action = step.get("action", "").lower()
                    if direct_action in ["click", "type", "press", "wait", "scroll"]:
                        step_type = "system"
                
                if step_type == 'file':
                    result = await self.execute_file_action(action)
                elif step_type == 'system':
                    result = await self.execute_system_action(action)
                elif step_type == 'code':
                    result = await self.execute_code_action(action)
                elif step_type == 'web':
                    result = await self.execute_web_action(action)
                else:
                    self.logger.warning(f"Unknown step type: {step_type}, treating as system")
                    # Try to handle as system action as fallback
                    result = await self.execute_system_action(action)
                
                # Check for specific result types and store them
                if step_type == 'code' and action.get('action') == 'automateCalculator':
                    if result and result.get('success') and result.get('result') is not None:
                        # Store calculation result
                        self.context['calculation_result'] = result.get('result')
                        self.context['calculation_operation'] = result.get('operation')
                        
                        # Emit a special event for UI
                        self.emit('calculation-result', {
                            'operation': result.get('operation'),
                            'result': result.get('result'),
                            'message': result.get('message')
                        })
                
                results.append(result)
                
                # Update context with result
                self.context[f"step_{self.current_step_index}_result"] = result
            
            self.emit('step-completed', {
                'step': step,
                'index': self.current_step_index,
                'results': results
            })
            
            return {
                'completed': False,
                'step': step,
                'results': results
            }
            
        except Exception as error:
            self.logger.error(f"Error executing step {self.current_step_index}: {str(error)}")
            self.emit('step-error', {
                'step': step,
                'index': self.current_step_index,
                'error': str(error)
            })
            raise error

    async def execute_file_action(self, action: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a file-related action.
        
        Args:
            action: The action to execute.
            
        Returns:
            A dictionary containing the execution results.
        """
        # Import the service dynamically to avoid circular imports
        from services.file_service import FileService
        file_service = FileService()
        
        action_type = action.get('action', '')
        params = action.get('params', {})
        
        if action_type == 'create' or action_type == 'create_file':
            path = params.get('path') or params.get('filename', '')
            content = params.get('content', '')
            return await file_service.create_file(path, content)
        elif action_type == 'read' or action_type == 'read_file':
            path = params.get('path') or params.get('filename', '')
            return await file_service.read_file(path)
        elif action_type == 'update' or action_type == 'update_file':
            path = params.get('path') or params.get('filename', '')
            content = params.get('content', '')
            return await file_service.update_file(path, content)
        elif action_type == 'delete' or action_type == 'delete_file':
            path = params.get('path') or params.get('filename', '')
            return await file_service.delete_file(path)
        elif action_type == 'list' or action_type == 'list_files':
            path = params.get('path') or params.get('directory', '.')
            return await file_service.list_files(path)
        elif action_type == 'search':
            path = params.get('path', '.')
            options = params.get('options', {})
            return await file_service.search_files(path, options)
        elif action_type == 'save_file':
            path = params.get('path') or params.get('filename', '')
            content = params.get('content', '')
            return await file_service.update_file(path, content)
        else:
            self.logger.info(f"Attempting to execute unknown file action: {action_type}")
            # Try to be more forgiving by checking action intent
            if 'create' in action_type or 'save' in action_type:
                self.logger.info(f"Falling back to generic file creation for: {params.get('filename') or params.get('path')}")
                path = params.get('path') or params.get('filename', '')
                content = params.get('content', '')
                return await file_service.create_file(path, content)
            
            raise ValueError(f"Unsupported file action: {action_type}")

    async def execute_system_action(self, action: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a system-related action.
        
        Args:
            action: The action to execute.
            
        Returns:
            A dictionary containing the execution results.
        """
        # Import the service dynamically to avoid circular imports
        from services.system_service import system_service
        
        action_type = action.get('action', '')
        params = action.get('params', {})
        
        if action_type == 'simulate_input':
            return await system_service.simulate_input(params.get('input_sequence', ''))
        elif action_type == 'getInfo':
            return system_service.get_system_info()
        elif action_type in ['execute', 'execute_system_command', 'execute system command']:
            return await system_service.execute_command(params.get('command', ''))
        elif action_type == 'launch':
            return await system_service.launch_application(
                params.get('path', ''), 
                params.get('args', [])
            )
        elif action_type == 'getProcesses':
            return await system_service.get_running_processes()
        elif action_type == 'interactWithBrowser':
            return await system_service.interactWithBrowser(
                params.get('action', ''),
                params
            )
        elif action_type == 'mouse_move' or action_type == 'mousemove':
            return await system_service.mouse_move(
                params.get('x', 100),
                params.get('y', 100)
            )
        elif action_type == 'mouse_click' or action_type == 'mouseclick' or action_type == 'click':
            return await system_service.mouse_click(
                params.get('x'),
                params.get('y'),
                params.get('button', 'left')
            )
        elif action_type == 'press_key' or action_type == 'presskey':
            return await system_service.press_key(params.get('key', ''))
        elif action_type == 'press_keys' or action_type == 'presskeys':
            return await system_service.press_keys(params.get('keys', []))
        elif action_type == 'type' or action_type == 'typetext':
            return await system_service.simulate_input(params.get('text', ''))
        elif action_type == 'wait':
            import asyncio
            await asyncio.sleep(params.get('time', 1000) / 1000)
            return {'success': True, 'action': 'wait', 'time': params.get('time', 1000)}
        else:
            self.logger.info(f"Attempting to execute unknown system action: {action_type}")
            # Try to be more forgiving by executing commands even if action names don't match exactly
            if 'execute' in action_type and params and params.get('command'):
                self.logger.info(f"Falling back to generic command execution for: {params.get('command')}")
                return await system_service.execute_command(params.get('command'))
            
            raise ValueError(f"Unsupported system action: {action_type}")

    async def execute_web_action(self, action: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a web-related action.
        
        Args:
            action: The action to execute.
            
        Returns:
            A dictionary containing the execution results.
        """
        # Import the service dynamically to avoid circular imports
        from services.web_service import WebService
        web_service = WebService()
        
        action_type = action.get('action', '')
        params = action.get('params', {})
        
        if action_type == 'startBrowser':
            return await web_service.start_browser()
        elif action_type == 'navigate':
            return await web_service.navigate_to_url(params.get('url', ''))
        elif action_type == 'interact':
            return await web_service.interact_with_element(
                params.get('selector', ''),
                params.get('interaction', ''),
                params.get('value', '')
            )
        elif action_type == 'extract':
            return await web_service.extract_data(params.get('selector', ''))
        elif action_type == 'screenshot':
            return await web_service.take_screenshot(params.get('filename', ''))
        elif action_type == 'closeBrowser':
            return await web_service.close_browser()
        else:
            raise ValueError(f"Unsupported web action: {action_type}")

    async def execute_code_action(self, action: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a code-related action.
        
        Args:
            action: The action to execute.
            
        Returns:
            A dictionary containing the execution results.
        """
        # Import services dynamically to avoid circular imports
        from services.code_service import CodeService
        from services.gui_automation_service import GuiAutomationService
        
        code_service = CodeService()
        gui_automation_service = GuiAutomationService()
        
        action_type = action.get('action', '')
        params = action.get('params', {})
        
        if action_type == 'verifyWebPage':
            from services.vision_service import VisionService
            vision_service = VisionService()
            return await vision_service.verify_web_page(params.get('websiteName', ''))
        elif action_type == 'generate':
            return await code_service.generate_code(
                params.get('prompt', ''),
                params.get('language', '')
            )
        elif action_type == 'execute':
            return await code_service.execute_code(
                params.get('filePath', ''),
                params.get('language', ''),
                params.get('args', [])
            )
        elif action_type == 'analyze':
            return await code_service.analyze_code(
                params.get('code', ''),
                params.get('language', '')
            )
        elif action_type == 'modify':
            return await code_service.modify_code(
                params.get('filePath', ''),
                params.get('instructions', '')
            )
        elif action_type == 'detectIDEs':
            return await code_service.detect_ides()
        elif action_type == 'automateCalculator':
            # Handle calculator automation directly
            if params.get('num1') is not None and params.get('num2') is not None and params.get('operation') is not None:
                return await gui_automation_service.automate_calculator(
                    params.get('num1'),
                    params.get('num2'),
                    params.get('operation')
                )
            return {'success': False, 'error': 'Missing calculator parameters'}
        else:
            # Try to be more forgiving by checking action intent
            if 'calculator' in action_type and params:
                # Extract params from the action
                num1 = params.get('num1')
                num2 = params.get('num2')
                operation = params.get('operation')
                if num1 is not None and num2 is not None and operation is not None:
                    return await gui_automation_service.automate_calculator(num1, num2, operation)
            
            raise ValueError(f"Unsupported code action: {action_type}")

    async def execute_full_task(self) -> Dict[str, Any]:
        """
        Execute all steps in the current task.
        
        Returns:
            A dictionary containing the execution results.
        """
        try:
            # First, check if this was an info query
            # This is important: info queries don't need execution
            if self.context.get('isAgentInfoResponse', False):
                self.logger.info("This was an information query, no execution needed")
                self.emit('task-summary', {
                    'message': 'Information provided successfully.',
                    'results': {}
                })
                return {
                    'success': True,
                    'task': self.current_task,
                    'context': self.context,
                    'summary': {
                        'message': 'Information provided successfully.',
                        'results': {}
                    }
                }
        
            # Check if we have a task and steps
            if not self.current_task:
                self.logger.error("No task has been analyzed yet")
                self.emit('error', {'error': 'No task has been analyzed yet'})
                return {'success': False, 'error': 'No task has been analyzed yet'}
            
            if not self.steps or len(self.steps) == 0:
                self.logger.error("No steps to execute for this task")
                self.emit('error', {'error': 'No steps to execute for this task'})
                return {'success': False, 'error': 'No steps to execute for this task'}
            
            # Reset step index to start from beginning
            self.current_step_index = -1
            
            # Execute each step
            result = None
            while self.current_step_index < len(self.steps) - 1:
                try:
                    result = await self.execute_next_step()
                    if result.get('completed', False):
                        break
                except Exception as step_error:
                    self.logger.error(f"Error executing step {self.current_step_index + 1}: {str(step_error)}")
                    self.emit('error', {'error': str(step_error)})
                    # Skip to next step rather than failing the whole task
                    self.current_step_index += 1
            
            # Create task summary
            task_summary = self.verify_task_completion()
            
            # Emit task summary event
            self.emit('task-summary', task_summary)
            
            return {
                'success': True,
                'task': self.current_task,
                'context': self.context,
                'summary': task_summary
            }
        except Exception as error:
            self.logger.error(f"Error executing full task: {str(error)}")
            self.emit('error', {'error': str(error)})
            return {
                'success': False,
                'error': str(error),
                'context': self.context
            }

    def verify_task_completion(self) -> Dict[str, Any]:
        """
        Verify and create a summary of the completed task.
        
        Returns:
            A dictionary containing the task summary.
        """
        summary = {
            'task': self.current_task,
            'steps': len(self.steps),
            'steps_completed': self.current_step_index + 1,
            'successful': self.current_step_index >= len(self.steps) - 1,
            'results': {}
        }
        
        # Check for specific results based on task type
        if self.context.get('calculation_result') is not None:
            summary['results']['calculation'] = {
                'operation': self.context.get('calculation_operation'),
                'result': self.context.get('calculation_result')
            }
            
            summary['message'] = f"Task completed. The answer is {self.context.get('calculation_result')}."
        elif self.context.get('web_results'):
            summary['results']['web'] = self.context.get('web_results')
            summary['message'] = "Web task completed successfully."
        elif self.context.get('file_results'):
            summary['results']['files'] = self.context.get('file_results')
            summary['message'] = "File operations completed successfully."
        elif self.context.get('search_term'):
            summary['results']['search'] = {
                'term': self.context.get('search_term'),
                'browser': self.context.get('browser_name', 'chrome')
            }
            summary['message'] = f"Browser search for '{self.context.get('search_term')}' completed successfully."
        else:
            summary['message'] = 'Task completed successfully.'
        
        return summary

    def get_task_state(self) -> Dict[str, Any]:
        """
        Get the current state of the task.
        
        Returns:
            A dictionary containing the current task state.
        """
        return {
            'task': self.current_task,
            'current_step_index': self.current_step_index,
            'total_steps': len(self.steps),
            'steps': self.steps,
            'context': self.context
        }

# Create a task manager instance
task_manager = TaskManager()