import os
import logging
import asyncio
import platform
import re
import tempfile
import subprocess
from pathlib import Path
from typing import Dict, List, Any, Union, Optional
import psutil

from utils.deepseek_client import DeepseekClient

class CodeService:
    """Service for code generation, execution, and management."""
    
    def __init__(self):
        """Initialize the CodeService."""
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)
        
        # Set up code directory
        self.code_directory = Path('generated_code')
        self.code_directory.mkdir(exist_ok=True)
        
        # Define supported languages and their execution settings
        self.supported_languages = {
            'javascript': {'extension': '.js', 'runner': 'node'},
            'python': {'extension': '.py', 'runner': 'python'},
            'html': {'extension': '.html', 'runner': None},
            'css': {'extension': '.css', 'runner': None},
            'batch': {'extension': '.bat', 'runner': 'cmd /c' if platform.system() == 'Windows' else 'sh'},
            'powershell': {'extension': '.ps1', 'runner': 'powershell -ExecutionPolicy Bypass -File' if platform.system() == 'Windows' else 'pwsh'}
        }
        
        # Initialize DeepSeek client for code generation
        self.deepseek_client = DeepseekClient()
    
    async def generate_automation_code(self, task: str, target: Optional[str] = None) -> Dict[str, Any]:
        """
        Generate automation code for a specific task.
        
        Args:
            task: The task to automate.
            target: Optional target platform or application.
            
        Returns:
            Dictionary with generated code or error.
        """
        try:
            self.logger.info(f"Generating automation code for: {task}")
            
            # For calculator tasks, use a specialized prompt
            if 'calculator' in task.lower():
                # Extract numbers from the task
                number_pattern = r'(\d+)\s*(\+|\-|\*|\/)\s*(\d+)'
                match = re.search(number_pattern, task)
                
                prompt_content = ''
                
                if match:
                    num1, operation, num2 = match.groups()
                    prompt_content = f"""
                        Generate a Python script using PyAutoGUI to automate this calculator task:
                        1. Find and focus the calculator window
                        2. Clear any previous calculations
                        3. Type the number {num1}
                        4. Press the {operation} key
                        5. Type the number {num2}
                        6. Press Enter to get the result
                        
                        The script should be able to run and complete the entire calculation.
                    """
                else:
                    prompt_content = f"""
                        Generate a Python script using PyAutoGUI to automate this calculator task: "{task}"
                        The script should be able to find the calculator window, interact with it, and perform the calculation.
                    """
                
                code_result = await self.generate_code(prompt_content, 'python')
                return code_result
            
            # More general automation
            prompt = f"""
                Create automation code for the following task: "{task}"
                Target: {target or "Windows desktop"}
                
                Use the appropriate library based on the task:
                - For GUI automation: Use PyAutoGUI
                - For web automation: Use Playwright or Selenium
                - For system automation: Use appropriate system commands
                
                Make sure the code is executable and includes all necessary error handling.
                The code should be well-commented to explain what each section does.
            """
            
            return await self.generate_code(prompt, 'python')
        except Exception as error:
            self.logger.error(f"Error generating automation code: {str(error)}")
            return {'success': False, 'error': str(error)}
    
    def strip_markdown_code_blocks(self, code: str) -> str:
        """
        Helper function to strip markdown code blocks.
        
        Args:
            code: Code potentially containing markdown formatting.
            
        Returns:
            Clean code without markdown formatting.
        """
        # Remove markdown code block delimiters if present
        clean_code = code
        
        # Check for markdown code blocks (```language ... ```)
        code_block_regex = r'^```[\w]*\n([\s\S]*?)```$'
        match = re.search(code_block_regex, code)
        
        if match and match.group(1):
            clean_code = match.group(1)
        
        # Remove any remaining ``` markers at start/end
        clean_code = re.sub(r'^```[\w]*\n', '', clean_code)
        clean_code = re.sub(r'\n```$', '', clean_code)
        
        return clean_code.strip()
    
    async def generate_code(self, prompt: str, language: str, options: Dict[str, Any] = {}) -> Dict[str, Any]:
        """
        Generate code based on a prompt.
        
        Args:
            prompt: The prompt for code generation.
            language: Programming language to generate code in.
            options: Additional options for code generation.
            
        Returns:
            Dictionary with generated code or error.
        """
        try:
            language = language.lower()
            
            if language not in self.supported_languages:
                return {
                    'success': False,
                    'error': f"Unsupported language: {language}. Supported languages: {', '.join(self.supported_languages.keys())}"
                }
            
            self.logger.info(f"Generating {language} code for prompt: {prompt[:100]}...")
            
            # Get language information
            lang_info = self.supported_languages[language]
            
            # Create a prompt specifically for code generation
            json_prompt = f"""
                Write {language} code for the following request:
                "{prompt}"
                
                IMPORTANT: Provide ONLY the raw executable code. 
                Do NOT include markdown formatting, triple backticks, or language specifiers.
                Your response must be valid executable {language} code only that can be directly run.
            """
            
            # Generate code
            temperature = options.get('temperature', 0.2)
            code = await self.deepseek_client.generate_json(json_prompt, 3, 30)
            
            # Extract code from the response
            # If the response is a dict with an 'analysis' field, it's likely an error response
            if isinstance(code, dict) and 'analysis' in code:
                code_text = code.get('analysis', '')
            else:
                code_text = str(code)
            
            # Clean the code before saving
            clean_code = self.strip_markdown_code_blocks(code_text)
            
            # Create a unique filename
            import time
            timestamp = int(time.time())
            filename = f"{language}_{timestamp}{lang_info['extension']}"
            file_path = self.code_directory / filename
            
            # Save the code to a file
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(clean_code)
            
            return {
                'success': True,
                'language': language,
                'code': clean_code,
                'filename': filename,
                'filePath': str(file_path)
            }
        except Exception as error:
            self.logger.error(f"Error generating code: {str(error)}")
            return {'success': False, 'error': str(error)}
    
    async def execute_code(self, file_path: str, language: Optional[str] = None, args: List[str] = []) -> Dict[str, Any]:
        """
        Execute generated code.
        
        Args:
            file_path: Path to the code file to execute.
            language: Programming language of the code file.
            args: Command line arguments for execution.
            
        Returns:
            Dictionary with execution results or error.
        """
        try:
            # Check if file exists
            if not os.path.exists(file_path):
                return {'success': False, 'error': f"File not found: {file_path}"}
            
            # Determine language from file extension if not provided
            if not language:
                ext = os.path.splitext(file_path)[1].lower()
                language = next(
                    (lang for lang, info in self.supported_languages.items() 
                     if info['extension'] == ext),
                    None
                )
                
                if not language:
                    return {'success': False, 'error': f"Could not determine language for file: {file_path}"}
            
            language = language.lower()
            lang_info = self.supported_languages.get(language)
            
            if not lang_info:
                return {'success': False, 'error': f"Unsupported language: {language}"}
            
            if not lang_info.get('runner'):
                return {
                    'success': False,
                    'error': f"Execution not supported for {language} files. Files can be viewed but not executed directly."
                }
            
            self.logger.info(f"Executing {language} code from: {file_path}")
            
            # Build the command
            command = f"{lang_info['runner']} \"{file_path}\" {' '.join(args)}"
            self.logger.info(f"Running command: {command}")
            
            # Execute the command
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            # Wait for the process to complete and get output
            stdout, stderr = await process.communicate()
            
            # Decode output
            stdout_text = stdout.decode('utf-8', errors='replace')
            stderr_text = stderr.decode('utf-8', errors='replace')
            
            return {
                'success': True,
                'language': language,
                'filePath': file_path,
                'stdout': stdout_text,
                'stderr': stderr_text,
                'returncode': process.returncode
            }
        except Exception as error:
            self.logger.error(f"Error executing code: {str(error)}")
            return {
                'success': False,
                'error': str(error),
                'stderr': getattr(error, 'stderr', ''),
                'stdout': getattr(error, 'stdout', '')
            }
    
    async def analyze_code(self, code: str, language: str) -> Dict[str, Any]:
        """
        Analyze and explain code.
        
        Args:
            code: Code to analyze.
            language: Programming language of the code.
            
        Returns:
            Dictionary with code analysis or error.
        """
        try:
            self.logger.info(f"Analyzing {language} code...")
            
            # Make sure there's code to analyze
            if not code or not code.strip():
                return {'success': False, 'error': "No code provided for analysis"}
            
            # Clean the code just in case it has markdown
            clean_code = self.strip_markdown_code_blocks(code)
            
            # Create a prompt for code analysis
            prompt = f"""
                Analyze this {language} code and provide a brief explanation of what it does, 
                any potential issues, and suggestions for improvement:
                
                {clean_code}
                
                Format your analysis as:
                1. Purpose: [Brief description of what the code does]
                2. Key components: [Main functions/classes/features]
                3. Potential issues: [Any bugs, edge cases, or security concerns]
                4. Improvement suggestions: [Ways to make the code better]
            """
            
            # Generate analysis
            analysis = await self.deepseek_client.generate_json(prompt)
            
            # Extract analysis from response
            if isinstance(analysis, dict) and 'analysis' in analysis:
                analysis_text = analysis.get('analysis', '')
            else:
                analysis_text = str(analysis)
            
            return {
                'success': True,
                'language': language,
                'analysis': analysis_text
            }
        except Exception as error:
            self.logger.error(f"Error analyzing code: {str(error)}")
            return {'success': False, 'error': str(error)}
    
    async def modify_code(self, file_path: str, instructions: str) -> Dict[str, Any]:
        """
        Modify existing code based on instructions.
        
        Args:
            file_path: Path to the code file to modify.
            instructions: Instructions for code modification.
            
        Returns:
            Dictionary with modified code or error.
        """
        try:
            # Check if file exists
            if not os.path.exists(file_path):
                return {'success': False, 'error': f"File not found: {file_path}"}
            
            # Read the original code
            with open(file_path, 'r', encoding='utf-8') as f:
                original_code = f.read()
            
            # Determine language from file extension
            ext = os.path.splitext(file_path)[1].lower()
            language = next(
                (lang for lang, info in self.supported_languages.items() 
                 if info['extension'] == ext),
                None
            )
            
            if not language:
                return {'success': False, 'error': f"Could not determine language for file: {file_path}"}
            
            self.logger.info(f"Modifying {language} code based on instructions: {instructions}")
            
            # Create a prompt for code modification
            prompt = f"""
                Here is the original {language} code:
                {original_code}
                
                Modify this code according to these instructions:
                "{instructions}"
                
                IMPORTANT: Provide ONLY the raw executable code. 
                Do NOT include markdown formatting, triple backticks, or language specifiers.
                Your response must be valid executable {language} code only that can be directly run.
            """
            
            # Generate modified code
            modified_code_result = await self.deepseek_client.generate_json(prompt)
            
            # Extract modified code from the response
            if isinstance(modified_code_result, dict) and 'analysis' in modified_code_result:
                modified_code = modified_code_result.get('analysis', '')
            else:
                modified_code = str(modified_code_result)
            
            # Clean the code before saving
            clean_modified_code = self.strip_markdown_code_blocks(modified_code)
            
            # Create a new file for the modified code
            dir_path = os.path.dirname(file_path)
            base_name = os.path.splitext(os.path.basename(file_path))[0]
            new_file_path = os.path.join(dir_path, f"{base_name}_modified{ext}")
            
            # Save the modified code
            with open(new_file_path, 'w', encoding='utf-8') as f:
                f.write(clean_modified_code)
            
            return {
                'success': True,
                'language': language,
                'originalFilePath': file_path,
                'modifiedFilePath': new_file_path,
                'modifiedCode': clean_modified_code
            }
        except Exception as error:
            self.logger.error(f"Error modifying code: {str(error)}")
            return {'success': False, 'error': str(error)}
    
    async def detect_ides(self) -> Dict[str, Any]:
        """
        Detect and list running IDEs.
        
        Returns:
            Dictionary with list of running IDEs or error.
        """
        try:
            # Define IDE process names for different platforms
            ide_process_names = [
                {'name': 'Visual Studio Code', 'process': 'Code.exe' if platform.system() == 'Windows' else 'code'},
                {'name': 'Visual Studio', 'process': 'devenv.exe'},
                {'name': 'PyCharm', 'process': 'pycharm64.exe' if platform.system() == 'Windows' else 'pycharm'},
                {'name': 'IntelliJ IDEA', 'process': 'idea64.exe' if platform.system() == 'Windows' else 'idea'},
                {'name': 'Eclipse', 'process': 'eclipse.exe' if platform.system() == 'Windows' else 'eclipse'},
                {'name': 'Sublime Text', 'process': 'sublime_text.exe' if platform.system() == 'Windows' else 'sublime_text'},
                {'name': 'Atom', 'process': 'atom.exe' if platform.system() == 'Windows' else 'atom'}
            ]
            
            # Get list of running processes
            running_ides = []
            
            for proc in psutil.process_iter(['name']):
                try:
                    process_name = proc.info['name']
                    
                    # Check if process matches any IDE
                    for ide in ide_process_names:
                        if process_name.lower() == ide['process'].lower():
                            running_ides.append(ide['name'])
                            break
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    pass
            
            # Remove duplicates
            running_ides = list(set(running_ides))
            
            return {'success': True, 'runningIDEs': running_ides}
        except Exception as error:
            self.logger.error(f"Error detecting IDEs: {str(error)}")
            return {'success': False, 'error': str(error)}

# Export singleton instance
code_service = CodeService()