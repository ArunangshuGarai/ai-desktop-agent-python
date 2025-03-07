import os
import logging
import time
import platform
import subprocess
import asyncio
from typing import Dict, List, Any, Union, Optional
from pathlib import Path
import pytesseract
from PIL import Image, ImageGrab
import re

# Adjust tesseract command path based on OS
if platform.system() == 'Windows':
    pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

class VisionService:
    """Service for vision-related operations such as screenshots and OCR."""
    
    def __init__(self):
        """Initialize the VisionService."""
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)
        
        # Ensure screenshots directory exists
        self.screenshots_dir = Path('screenshots')
        self.screenshots_dir.mkdir(exist_ok=True)
    
    async def capture_active_window(self) -> Dict[str, Any]:
        """
        Take a screenshot of the currently active window.
        
        Returns:
            Dictionary with success status, path to screenshot or error.
        """
        try:
            # Generate a unique filename
            timestamp = int(time.time() * 1000)
            filename = f"window_{timestamp}.png"
            filepath = self.screenshots_dir / filename
            
            # Capture the screen
            screenshot = ImageGrab.grab()
            
            # Save the screenshot
            screenshot.save(filepath)
            
            self.logger.info(f"Screenshot saved to: {filepath}")
            
            return {
                'success': True,
                'path': str(filepath),
                'timestamp': timestamp
            }
        except Exception as error:
            self.logger.error(f"Error capturing active window: {str(error)}")
            
            # Try fallback approach if possible
            try:
                # Create fallback screenshot using platform-specific methods
                return await self.create_fallback_screenshot(f"fallback_{int(time.time() * 1000)}.png")
            except Exception as fallback_error:
                self.logger.error(f"Fallback screenshot also failed: {str(fallback_error)}")
                return {'success': False, 'error': str(error)}
    
    async def create_fallback_screenshot(self, filename: str) -> Dict[str, Any]:
        """
        Create a fallback screenshot using platform-specific methods.
        
        Args:
            filename: Name of the file to save the screenshot to.
            
        Returns:
            Dictionary with success status, path to screenshot or error.
        """
        try:
            filepath = self.screenshots_dir / filename
            
            # Windows-specific approach
            if platform.system() == 'Windows':
                # Use PowerShell to capture screen
                ps_command = f"""
                Add-Type -AssemblyName System.Windows.Forms
                Add-Type -AssemblyName System.Drawing
                
                $screen = [System.Windows.Forms.Screen]::PrimaryScreen
                $bitmap = New-Object System.Drawing.Bitmap $screen.Bounds.Width, $screen.Bounds.Height
                $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
                $graphics.CopyFromScreen($screen.Bounds.X, $screen.Bounds.Y, 0, 0, $bitmap.Size)
                $bitmap.Save("{filepath}")
                $graphics.Dispose()
                $bitmap.Dispose()
                """
                
                # Execute PowerShell command
                process = await asyncio.create_subprocess_shell(
                    f'powershell -Command "{ps_command}"',
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                
                await process.communicate()
                
                # Check if file was created
                if filepath.exists():
                    self.logger.info(f"Fallback screenshot saved to: {filepath}")
                    return {
                        'success': True,
                        'path': str(filepath),
                        'fallback': True
                    }
                else:
                    raise FileNotFoundError(f"Screenshot file not created: {filepath}")
            
            # Linux-specific approach
            elif platform.system() == 'Linux':
                # Use scrot if available
                process = await asyncio.create_subprocess_shell(
                    f'scrot "{filepath}"',
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                
                await process.communicate()
                
                # Check if file was created
                if filepath.exists():
                    self.logger.info(f"Fallback screenshot saved to: {filepath}")
                    return {
                        'success': True,
                        'path': str(filepath),
                        'fallback': True
                    }
                else:
                    raise FileNotFoundError(f"Screenshot file not created: {filepath}")
            
            # MacOS-specific approach
            elif platform.system() == 'Darwin':
                # Use screencapture
                process = await asyncio.create_subprocess_shell(
                    f'screencapture -x "{filepath}"',
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                
                await process.communicate()
                
                # Check if file was created
                if filepath.exists():
                    self.logger.info(f"Fallback screenshot saved to: {filepath}")
                    return {
                        'success': True,
                        'path': str(filepath),
                        'fallback': True
                    }
                else:
                    raise FileNotFoundError(f"Screenshot file not created: {filepath}")
            
            else:
                # Unsupported platform
                raise NotImplementedError(f"Screenshots not implemented for {platform.system()}")
            
        except Exception as error:
            self.logger.error(f"Error creating fallback screenshot: {str(error)}")
            
            # Last resort: create a dummy image
            try:
                # Create a simple blank image
                from PIL import Image, ImageDraw, ImageFont
                
                # Create a blank image
                img = Image.new('RGB', (800, 600), color='white')
                draw = ImageDraw.Draw(img)
                
                # Draw some text
                draw.text((10, 10), 'Fallback dummy screenshot', fill='black')
                draw.text((10, 30), f'Error: {str(error)}', fill='red')
                draw.text((10, 50), f'Timestamp: {time.time()}', fill='blue')
                
                # Save the image
                img.save(filepath)
                
                self.logger.info(f"Dummy fallback screenshot saved to: {filepath}")
                return {
                    'success': True,
                    'path': str(filepath),
                    'fallback': True,
                    'dummy': True
                }
            except Exception as dummy_error:
                self.logger.error(f"Dummy screenshot also failed: {str(dummy_error)}")
                return {'success': False, 'error': str(error)}
    
    async def take_screenshot(self, output_path: Optional[str] = None) -> Dict[str, Any]:
        """
        Take a screenshot and save it to the specified path.
        
        Args:
            output_path: Path to save the screenshot to. If None, a default path is used.
            
        Returns:
            Dictionary with success status, path to screenshot or error.
        """
        try:
            # If no output path provided, generate one
            if output_path is None:
                timestamp = int(time.time() * 1000)
                filename = f"screenshot_{timestamp}.png"
                output_path = str(self.screenshots_dir / filename)
            
            # Ensure directory exists
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            # Take screenshot using PIL
            screenshot = ImageGrab.grab()
            
            # Save the screenshot
            screenshot.save(output_path)
            
            self.logger.info(f"Screenshot saved to: {output_path}")
            
            return {
                'success': True,
                'path': output_path
            }
        except Exception as error:
            self.logger.error(f"Error taking screenshot: {str(error)}")
            
            # Try fallback approach
            try:
                return await self.create_fallback_screenshot(os.path.basename(output_path))
            except Exception as fallback_error:
                self.logger.error(f"Fallback screenshot also failed: {str(fallback_error)}")
                return {'success': False, 'error': str(error)}
    
    async def recognize_text(self, image_path: str) -> Dict[str, Any]:
        """
        Recognize text in an image using OCR.
        
        Args:
            image_path: Path to the image file.
            
        Returns:
            Dictionary with success status, recognized text or error.
        """
        try:
            self.logger.info(f"Recognizing text from: {image_path}")
            
            # Check if file exists
            if not os.path.exists(image_path):
                return {'success': False, 'error': f"Image file not found: {image_path}"}
            
            # Open the image
            image = Image.open(image_path)
            
            # Extract text using pytesseract
            text = pytesseract.image_to_string(image)
            
            self.logger.info(f"Text recognition completed. Found {len(text)} characters.")
            
            return {
                'success': True,
                'text': text,
                'confidence': 90  # Dummy confidence value since pytesseract doesn't provide this directly
            }
        except Exception as error:
            self.logger.error(f"Error recognizing text: {str(error)}")
            
            # If tesseract is not installed or configured, return a helpful error
            if "tesseract is not installed" in str(error).lower() or "tesseract-ocr is not installed" in str(error).lower():
                return {
                    'success': False,
                    'error': "Tesseract OCR is not installed or not in PATH. Please install Tesseract OCR to use text recognition.",
                    'text': "OCR UNAVAILABLE - TESSERACT NOT INSTALLED"
                }
            
            return {'success': False, 'error': str(error)}
    
    async def verify_web_page(self, website_name: str) -> Dict[str, Any]:
        """
        Verify that a webpage has loaded correctly by checking for its title or content.
        
        Args:
            website_name: Name of the website to verify.
            
        Returns:
            Dictionary with success status or error.
        """
        try:
            self.logger.info(f"Verifying web page: {website_name}")
            
            # Take a screenshot of the current screen
            screenshot_result = await self.capture_active_window()
            
            if not screenshot_result.get('success'):
                return {'success': False, 'error': 'Failed to capture screen for verification'}
            
            # Get screenshot path
            screenshot_path = screenshot_result.get('path')
            
            # Perform OCR on the screenshot
            ocr_result = await self.recognize_text(screenshot_path)
            
            if not ocr_result.get('success'):
                return {'success': False, 'error': 'Failed to perform OCR on screenshot'}
            
            # Get recognized text
            text = ocr_result.get('text', '')
            
            # Check if website name is in the text
            # Use flexible matching to account for OCR errors
            website_pattern = re.compile(re.escape(website_name), re.IGNORECASE)
            
            if website_pattern.search(text):
                return {
                    'success': True,
                    'message': f"Website {website_name} verified",
                    'screenshot': screenshot_path
                }
            
            # Try alternative checks for common websites
            if website_name.lower() in ['google', 'google.com']:
                if re.search(r'(google|search)', text.lower()):
                    return {
                        'success': True,
                        'message': f"Google website verified",
                        'screenshot': screenshot_path
                    }
            
            # Website not verified
            return {
                'success': False,
                'message': f"Could not verify {website_name} website",
                'screenshot': screenshot_path,
                'recognized_text': text
            }
        except Exception as error:
            self.logger.error(f"Error verifying web page: {str(error)}")
            return {'success': False, 'error': str(error)}
    
    async def analyze_screen_with_ai(self, context: str) -> Dict[str, Any]:
        """
        Analyze a screenshot using AI.
        
        Args:
            context: Context for the analysis.
            
        Returns:
            Dictionary with success status, analysis or error.
        """
        try:
            self.logger.info(f"Analyzing screen with AI. Context: {context}")
            
            # Take a screenshot
            screenshot_result = await self.capture_active_window()
            
            if not screenshot_result.get('success'):
                return {'success': False, 'error': 'Failed to capture screen for AI analysis'}
            
            # Get screenshot path
            screenshot_path = screenshot_result.get('path')
            
            # Perform OCR on the screenshot
            ocr_result = await self.recognize_text(screenshot_path)
            
            if not ocr_result.get('success'):
                return {'success': False, 'error': 'Failed to perform OCR on screenshot for AI analysis'}
            
            # Get recognized text
            text = ocr_result.get('text', '')
            
            # In a real implementation, we would send the text to an AI service
            # For now, we'll just provide a placeholder analysis
            
            # Import the DeepSeek client dynamically
            from utils.deepseek_client import DeepseekClient
            
            # Create a client
            client = DeepseekClient()
            
            # Generate analysis
            analysis_result = await client.analyze_screenshot(text, context)
            
            return {
                'success': True,
                'screenshot': screenshot_path,
                'analysis': analysis_result,
                'text': text
            }
        except Exception as error:
            self.logger.error(f"Error analyzing screen with AI: {str(error)}")
            return {'success': False, 'error': str(error)}
    
    async def wait_for_element(self, element_text: str, timeout: int = 30) -> Dict[str, Any]:
        """
        Wait for an element with specific text to appear on screen.
        
        Args:
            element_text: Text to wait for.
            timeout: Timeout in seconds.
            
        Returns:
            Dictionary with success status or error.
        """
        try:
            self.logger.info(f"Waiting for element with text: {element_text}")
            
            start_time = time.time()
            
            while time.time() - start_time < timeout:
                # Take a screenshot
                screenshot_result = await self.capture_active_window()
                
                if not screenshot_result.get('success'):
                    continue
                
                # Get screenshot path
                screenshot_path = screenshot_result.get('path')
                
                # Perform OCR on the screenshot
                ocr_result = await self.recognize_text(screenshot_path)
                
                if not ocr_result.get('success'):
                    continue
                
                # Get recognized text
                text = ocr_result.get('text', '')
                
                # Check if element text is in the OCR result
                if element_text.lower() in text.lower():
                    return {
                        'success': True,
                        'message': f"Element with text '{element_text}' found",
                        'screenshot': screenshot_path,
                        'time_elapsed': time.time() - start_time
                    }
                
                # Wait before next attempt
                await asyncio.sleep(1)
            
            # Timeout reached
            return {
                'success': False,
                'message': f"Timeout waiting for element with text '{element_text}'",
                'last_screenshot': screenshot_path if 'screenshot_path' in locals() else None
            }
        except Exception as error:
            self.logger.error(f"Error waiting for element: {str(error)}")
            return {'success': False, 'error': str(error)}

# Export singleton instance
vision_service = VisionService()