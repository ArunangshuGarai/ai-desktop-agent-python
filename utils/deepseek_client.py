import os
import json
import re
import requests
import logging
from typing import Dict, List, Union, Optional, Any
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

class DeepseekClient:
    """Client for interacting with Deepseek models via OpenRouter API."""
    
    def __init__(self, api_key=None, endpoint=None, model=None):
        """
        Initialize the DeepseekClient.
        
        Args:
            api_key (str, optional): The OpenRouter API key. If None, uses environment variable.
            endpoint (str, optional): The API endpoint. If None, uses default OpenRouter endpoint.
            model (str, optional): The model name to use. If None, uses default model.
        """
        self.api_key = api_key or os.getenv("OPENROUTER_API_KEY")
        self.endpoint = endpoint or "https://openrouter.ai/api/v1/chat/completions"
        self.model = model or "deepseek/deepseek-r1:free"
        self.site_url = "https://ai-desktop-agent"
        self.site_name = "AI Desktop Agent"
        
        # Check if API key is missing or empty
        if not self.api_key or self.api_key.strip() == "":
            logger.warning("WARNING: OpenRouter API key is missing - using mock responses instead")
            self.use_mock_responses = True
        else:
            self.use_mock_responses = False
        
        # Agent identity information
        self.agent_info = {
            "name": "AI Desktop Agent",
            "version": "1.0.0",
            "purpose": "I'm an AI desktop agent designed to help you automate tasks on your computer. "
                      "I can analyze screen content, control your mouse and keyboard, and execute "
                      "workflows based on visual information.",
            "capabilities": [
                "Take screenshots of your desktop",
                "Analyze screen content to understand what's visible",
                "Automate mouse clicks and keyboard inputs",
                "Execute multi-step desktop workflows",
                "Break down complex tasks into simple steps",
                "Adapt to different applications and interfaces"
            ],
            "limitations": [
                "I can only interact with what's visible on screen",
                "I need clear instructions for complex tasks",
                "I may require confirmation for certain actions",
                "I operate within the boundaries of your desktop environment"
            ]
        }
        
        logger.info(f"DeepseekClient initialized with OpenRouter, "
                  f"{'using mock responses' if self.use_mock_responses else 'using API endpoint'}")
        logger.info(f"Target model: {self.model}")

    def is_agent_info_query(self, query: str) -> bool:
        """
        Detect if a query is asking about the agent itself.
        
        Args:
            query (str): The user query to analyze.
            
        Returns:
            bool: True if query is about the agent.
        """
        if not query:
            return False
        
        lower_query = query.lower()
        self_referential_patterns = [
            'what can you do',
            'what are you',
            'who are you',
            'your purpose',
            'your capabilities',
            'what do you do',
            'how do you work',
            'how does this work',
            'what is this',
            'help me',
            'your function',
            'your features',
            'your abilities',
            'tell me about yourself',
            'introduce yourself',
            'your limitations',
            'what can\'t you do',
            'your name'
        ]
        
        return any(pattern in lower_query for pattern in self_referential_patterns)

    # Improved generate_json method with better error handling and reduced timeout

    async def generate_json(self, prompt: str, retries: int = 3, timeout: int = 15) -> Dict[str, Any]:
        """
        Generate JSON-formatted analysis from a prompt.
        
        Args:
            prompt (str): The prompt to analyze.
            retries (int, optional): Number of retry attempts. Defaults to 3.
            timeout (int, optional): Request timeout in seconds. Defaults to 15.
            
        Returns:
            Dict[str, Any]: The parsed JSON response.
        """
        # Check if we should use mock responses
        if self.use_mock_responses:
            logger.info(f"Using mock response for prompt: {prompt[:100]}...")
            return self.get_mock_response(prompt)
        
        # Enhance the prompt based on its content
        enhanced_prompt = self.enhance_prompt(prompt)
        
        attempt = 0
        last_error = None
        
        while attempt < retries:
            attempt += 1
            logger.info(f"API request attempt {attempt}/{retries} to OpenRouter")
            
            try:
                # Prepare headers
                headers = {
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.api_key}",
                    "HTTP-Referer": self.site_url,
                    "X-Title": self.site_name
                }
                
                # Prepare request body
                body = {
                    "model": self.model,
                    "messages": [
                        {"role": "user", "content": enhanced_prompt}
                    ],
                    "temperature": 0.2,
                    "max_tokens": 4000
                }
                
                import aiohttp
                
                # More robust error handling
                try:
                    # First attempt with aiohttp
                    async with aiohttp.ClientSession() as session:
                        async with session.post(
                            self.endpoint,
                            headers=headers,
                            json=body,
                            timeout=aiohttp.ClientTimeout(total=timeout)
                        ) as response:
                            response.raise_for_status()
                            response_data = await response.json()
                except ImportError:
                    # Fallback to synchronous requests if aiohttp is not available
                    logger.warning("aiohttp not available, falling back to synchronous requests")
                    import requests
                    import json
                    
                    response = requests.post(
                        self.endpoint,
                        headers=headers,
                        json=body,
                        timeout=timeout
                    )
                    response.raise_for_status()
                    response_data = response.json()
                
                logger.info(f"Raw API response received. First 500 chars: {str(response_data)[:500]}...")
                
                if not response_data.get("choices") or not response_data["choices"][0].get("message"):
                    raise ValueError("Unexpected API response format")
                
                message_content = response_data["choices"][0]["message"]["content"]
                
                # If this was an agent info query, format the response appropriately
                if self.is_agent_info_query(prompt):
                    return self.format_agent_info_response(message_content)
                
                return self.extract_and_parse_json(message_content)
            
            except Exception as e:
                last_error = e
                error_type = type(e).__name__
                error_message = str(e)
                logger.error(f"API request error (attempt {attempt}/{retries}): {error_type}: {error_message}")
                
                if attempt < retries:
                    import asyncio
                    wait_time = attempt * 2
                    logger.info(f"Retrying in {wait_time} seconds...")
                    await asyncio.sleep(wait_time)
                    continue
        
        # If all retries failed, return a fallback response
        logger.error(f"All API request attempts failed. Last error: {type(last_error).__name__}: {str(last_error)}")
        
        # Create appropriate fallback response
        if self.is_agent_info_query(prompt):
            return self.create_agent_info_fallback()
        else:
            return self.create_fallback_response(
                f"API request failed after {retries} attempts. Using fallback analysis. Error: {str(last_error)}"
            )
        
    def get_mock_response(self, prompt: str) -> Dict[str, Any]:
        """
        Get a mock response when no API key is available.
        
        Args:
            prompt (str): The original prompt.
            
        Returns:
            Dict[str, Any]: A mock response object.
        """
        # For agent info queries, return the agent info
        if self.is_agent_info_query(prompt):
            return self.create_agent_info_fallback()
        
        # For browser tasks, return a specialized task breakdown
        if any(term in prompt.lower() for term in ['browser', 'chrome', 'firefox']) and any(term in prompt.lower() for term in ['search', 'navigate', 'open']):
            search_term = "python"  # Default search term
            
            # Try to extract search term
            import re
            search_match = re.search(r'search\s+(?:for\s+)?([a-zA-Z0-9\s]+)(?:\s+in|\s+with|\s+using)?', 
                                  prompt.lower(), re.IGNORECASE)
            if search_match:
                search_term = search_match.group(1).strip()
                
            return {
                "analysis": f"I'll help you search for '{search_term}' in your browser.",
                "steps": [
                    {
                        "description": "Launch Chrome browser",
                        "action": "execute",
                        "params": {
                            "command": "start chrome"
                        }
                    },
                    {
                        "description": f"Search for '{search_term}'",
                        "action": "interactWithBrowser",
                        "params": {
                            "action": "search",
                            "searchText": search_term
                        }
                    }
                ]
            }
            
        # For regular tasks, return a basic task breakdown
        return {
            "analysis": f"I'll help you with \"{prompt}\". Without API access, I'll provide a basic response.",
            "steps": [
                {
                    "description": "Take a screenshot to analyze the current state",
                    "action": "screenshot",
                    "target": None
                },
                {
                    "description": "Wait briefly for system to stabilize",
                    "action": "wait",
                    "time": 1000
                },
                {
                    "description": "This is a mock step (API key not configured)",
                    "action": "mock",
                    "target": None
                }
            ]
        }
    
    def format_agent_info_response(self, response_text: str) -> Dict[str, Any]:
        """
        Format a response about the agent's capabilities.
        
        Args:
            response_text (str): The raw response from the API.
            
        Returns:
            Dict[str, Any]: Formatted response object.
        """
        # Format the response to make it more readable
        formatted_response = response_text
        # Replace bullet points to improve readability
        formatted_response = formatted_response.replace("•", "• ")
        formatted_response = re.sub(r'\n- ', '\n• ', formatted_response)
        formatted_response = formatted_response.replace("* ", "• ")
        # Add spacing after paragraphs
        formatted_response = formatted_response.replace("\n\n", "\n\n")
        # Ensure proper spacing after periods
        formatted_response = re.sub(r'\.(?=[A-Z])', '. ', formatted_response)
        
        return {
            "analysis": formatted_response,
            "isAgentInfoResponse": True,
            "steps": [
                {
                    "description": "Take a screenshot to help you visualize the current state",
                    "action": "screenshot",
                    "target": None
                }
            ]
        }
    
    def create_agent_info_fallback(self) -> Dict[str, Any]:
        """
        Create a fallback response about the agent when API fails.
        
        Returns:
            Dict[str, Any]: Fallback agent info response.
        """
        capabilities_text = "\n".join([f"- {c}" for c in self.agent_info["capabilities"]])
        limitations_text = "\n".join([f"- {l}" for l in self.agent_info["limitations"]])
        
        return {
            "analysis": f"{self.agent_info['purpose']}\n\nI can help you with:\n{capabilities_text}\n\n"
                       f"My limitations:\n{limitations_text}",
            "isAgentInfoResponse": True,
            "steps": [
                {
                    "description": "Take a screenshot to help you visualize the current state",
                    "action": "screenshot",
                    "target": None
                }
            ]
        }
    
    def enhance_prompt(self, prompt: str) -> str:
        """
        Enhance a prompt with additional context based on its content.
        
        Args:
            prompt (str): The original prompt.
            
        Returns:
            str: Enhanced prompt with additional context.
        """
        # If the query is about the agent itself, provide relevant context
        if self.is_agent_info_query(prompt):
            return self.generate_agent_info_prompt(prompt)
        
        # For browser search tasks, use specialized prompt
        if any(term in prompt.lower() for term in ['browser', 'chrome', 'firefox']) and any(term in prompt.lower() for term in ['search', 'navigate', 'open']):
            return self.generate_browser_prompt(prompt)
            
        # For task-based prompts, use the structured format
        return self.generate_structured_prompt(prompt)
    
    def generate_agent_info_prompt(self, query: str) -> str:
        """
        Generate a prompt specifically for agent information queries.
        
        Args:
            query (str): The original query about the agent.
            
        Returns:
            str: Enhanced prompt with agent context.
        """
        capabilities_text = ", ".join(self.agent_info["capabilities"])
        limitations_text = ", ".join(self.agent_info["limitations"])
        
        return f"""You are {self.agent_info["name"]}, an AI desktop automation agent. 
When responding to this query, speak in first person as if you are the AI agent running on the user's computer.

The user is asking: "{query}"

Respond conversationally as the AI desktop agent, using these facts about yourself:
- Your purpose: {self.agent_info["purpose"]}
- Your capabilities: {capabilities_text}
- Your limitations: {limitations_text}

Your response should be helpful, conversational, and reflect your identity as a desktop automation tool.
Do not mention that you're using an API or that you're running on a language model.
Speak as if you are directly the AI agent software that's installed on their computer."""
    
    def generate_browser_prompt(self, query: str) -> str:
        """
        Generate a specialized prompt for browser-related tasks.
        
        Args:
            query (str): The original browser task query.
            
        Returns:
            str: Enhanced prompt for browser tasks.
        """
        return f"""
I need to help the user with this browser-related task:
"{query}"

I am {self.agent_info["name"]}, a desktop automation tool that can control the browser.

Analyze this browser task and return a detailed JSON object with:
{{
  "analysis": "Brief explanation of what this browser task requires",
  "steps": [
    {{
      "description": "Clear step description",
      "action": "execute or interactWithBrowser",
      "params": {{
        "command": "start chrome" or
        "action": "search or navigate",
        "searchText": "text to search for",
        "url": "url to navigate to"
      }}
    }}
  ]
}}

Be specific about extracting any search terms or URLs from the task.
Ensure the steps are concrete and executable with proper mouse/keyboard actions.
"""
    
    def generate_structured_prompt(self, base_prompt: str) -> str:
        """
        Generate a structured prompt for task analysis.
        
        Args:
            base_prompt (str): The original task prompt.
            
        Returns:
            str: Enhanced prompt with clear instructions.
        """
        return f"""
I need to break down this desktop automation task into vision-based steps:
"{base_prompt}"

I am {self.agent_info["name"]}, a desktop automation tool that can analyze screen content and perform actions.

Analyze this task and return a JSON object with the following structure:
{{
  "analysis": "Brief analysis of what needs to be done",
  "steps": [
    {{
      "description": "Clear description of the step",
      "action": "One of: click, type, screenshot, wait, press, scroll, dragdrop",
      "target": {{"x": 100, "y": 200}} or null depending on the action,
      "text": "Text to type if action is type",
      "time": 1000 if action is wait (milliseconds)
    }}
  ]
}}

Make sure each step is atomic and has exactly one clear action. All JSON fields must be properly formatted with no trailing commas.
"""
    
    def extract_and_parse_json(self, response_text: str) -> Dict[str, Any]:
        """
        Extract and parse JSON from API response text.
        Enhanced with multiple fallback strategies for robust parsing.
        
        Args:
            response_text (str): The response text to parse.
            
        Returns:
            Dict[str, Any]: The parsed JSON object.
        """
        if not response_text:
            logger.error("Response text is empty")
            return self.create_fallback_response("Empty response from API")
        
        try:
            # First attempt: direct JSON parsing
            return json.loads(response_text)
        except json.JSONDecodeError as error:
            logger.info("Direct JSON parsing failed, trying alternatives...")
            
            try:
                # Second attempt: Try to extract JSON using regex
                json_match = re.search(r'\{[\s\S]*\}', response_text)
                if json_match:
                    return json.loads(json_match.group(0))
            except (json.JSONDecodeError, AttributeError):
                logger.info("JSON extraction with regex failed...")
            
            try:
                # Third attempt: Fix common JSON syntax issues
                fixed_json = response_text
                fixed_json = re.sub(r'\n', ' ', fixed_json)
                fixed_json = re.sub(r'\s+', ' ', fixed_json)
                fixed_json = re.sub(r',\s*\}', '}', fixed_json)
                fixed_json = re.sub(r',\s*\]', ']', fixed_json)
                
                return json.loads(fixed_json)
            except json.JSONDecodeError:
                logger.info("JSON syntax fixing failed too...")
            
            try:
                # Fourth attempt: If all else fails, try to create a valid JSON structure
                last_open_brace = response_text.rfind('{')
                last_close_brace = response_text.rfind('}')
                
                if last_open_brace >= 0 and last_close_brace > last_open_brace:
                    json_substring = response_text[last_open_brace:last_close_brace + 1]
                    return json.loads(json_substring)
            except json.JSONDecodeError:
                logger.info("JSON substring extraction failed...")
            
            try:
                # Fifth attempt: Try to extract a JSON-like structure and build it manually
                analysis_match = re.search(r'["|\']analysis["|\']\\s*:\\s*["|\']([^"|\']*)["|\'"]', response_text)
                if analysis_match and analysis_match.group(1):
                    return self.create_fallback_response(analysis_match.group(1))
            except (AttributeError, IndexError):
                logger.info("Analysis extraction failed...")
            
            # If everything fails, create a fallback response
            logger.error(f"Could not parse JSON. Original error: {str(error)}")
            return self.create_fallback_response("Failed to parse API response. Using fallback analysis.")
    
    def create_fallback_response(self, message: str) -> Dict[str, Any]:
        """
        Create a fallback response when parsing fails.
        
        Args:
            message (str): The message to include in the fallback.
            
        Returns:
            Dict[str, Any]: A structured fallback response.
        """
        return {
            "analysis": message,
            "steps": [
                {
                    "description": "Take screenshot to assess current state",
                    "action": "screenshot",
                    "target": None
                },
                {
                    "description": "Wait for system to stabilize",
                    "action": "wait",
                    "time": 2000
                }
            ]
        }
    
    async def analyze_screenshot(self, text_content: str, task: str) -> Dict[str, Any]:
        """
        Analyze a screenshot using text content.
        
        Args:
            text_content (str): The text extracted from the screenshot.
            task (str): The task description.
            
        Returns:
            Dict[str, Any]: Analysis result.
        """
        prompt = f"""
I am {self.agent_info["name"]}, analyzing a screenshot with the following text content:

{text_content}

Based on this text content and the user's task: "{task}"

Analyze what's visible on screen and return a JSON object with:
{{
  "analysis": "Detailed analysis of what's visible on screen and how it relates to the task",
  "elements": [
    {{
      "type": "button|text|input|menu|link",
      "text": "Text of the element",
      "likely_location": "top-left|top|top-right|left|center|right|bottom-left|bottom|bottom-right",
      "confidence": 0.8,
      "relevance_to_task": "high|medium|low",
      "suggested_action": "click|type|none"
    }}
  ],
  "next_steps": [
    {{
      "description": "Clear description of the step",
      "action": "One of: click, type, screenshot, wait, press, scroll, dragdrop",
      "target": {{"location": "description of where to click"}},
      "text": "Text to type if action is type" 
    }}
  ]
}}
"""

        return await self.generate_json(prompt)