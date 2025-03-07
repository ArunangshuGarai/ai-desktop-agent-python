import sys
import os
import logging
import asyncio
import argparse
from pathlib import Path
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('ai_desktop_agent.log')
    ]
)
logger = logging.getLogger(__name__)

# Load environment variables from .env file
load_dotenv()

def setup_directories():
    """Ensure all required directories exist."""
    Path('screenshots').mkdir(exist_ok=True)
    Path('generated_code').mkdir(exist_ok=True)


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='AI Desktop Agent')
    parser.add_argument('--no-gui', action='store_true', help='Run in command-line mode without GUI')
    parser.add_argument('--task', type=str, help='Task to execute in command-line mode')
    parser.add_argument('--debug', action='store_true', help='Enable debug logging')
    
    return parser.parse_args()


async def run_task(task):
    """
    Run a single task in command-line mode.
    
    Args:
        task: Task description to execute.
        
    Returns:
        Task execution result.
    """
    from core.task_manager import task_manager
    
    try:
        logger.info(f"Analyzing task: {task}")
        analysis_result = await task_manager.analyze_task(task)
        
        logger.info(f"Executing task: {task}")
        execution_result = await task_manager.execute_full_task()
        
        return execution_result
    except Exception as e:
        logger.error(f"Error executing task: {str(e)}")
        return {"success": False, "error": str(e)}


async def cli_mode(task):
    """
    Run the application in command-line mode.
    
    Args:
        task: Task description to execute.
    """
    if not task:
        print("Error: --task argument is required in command-line mode")
        print("Usage: python main.py --no-gui --task \"Your task description\"")
        return 1
    
    try:
        print(f"AI Desktop Agent - Command Line Mode")
        print(f"Executing task: {task}")
        
        result = await run_task(task)
        
        if result.get("success"):
            print("\nTask completed successfully!")
            
            # Print summary
            summary = result.get("summary", {})
            if summary:
                print(f"\nSummary: {summary.get('message', '')}")
                
                # Print calculation results if available
                calc_result = summary.get("results", {}).get("calculation")
                if calc_result:
                    print(f"Result: {calc_result.get('operation')} = {calc_result.get('result')}")
            
            return 0
        else:
            print(f"\nTask failed: {result.get('error', 'Unknown error')}")
            return 1
    except KeyboardInterrupt:
        print("\nOperation cancelled by user")
        return 130
    except Exception as e:
        print(f"\nAn error occurred: {str(e)}")
        logger.exception("Unhandled exception in CLI mode")
        return 1


def gui_mode():
    """Run the application in GUI mode."""
    try:
        # Import Qt modules and UI components here to avoid import errors
        # when running in CLI mode without PyQt installed
        from PyQt6.QtWidgets import QApplication
        from ui.main_window import MainWindow
        
        # Create application
        app = QApplication(sys.argv)
        app.setStyle("Fusion")
        
        # Create and show main window
        window = MainWindow()
        window.show()
        
        # Start the event loop
        return app.exec()
    except KeyboardInterrupt:
        logger.info("Application terminated by user")
        return 130
    except Exception as e:
        logger.exception("Unhandled exception in GUI mode")
        return 1


def setup_asyncio_event_loop():
    """Set up the asyncio event loop for the current platform."""
    if sys.platform == 'win32':
        # On Windows, use the ProactorEventLoop
        loop = asyncio.ProactorEventLoop()
        asyncio.set_event_loop(loop)
    else:
        # On other platforms, use the default event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    return loop


def main():
    """Main entry point for the application."""
    # Ensure directories exist
    setup_directories()
    
    # Parse command line arguments
    args = parse_args()
    
    # Configure logging level
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
        logger.debug("Debug logging enabled")
    
    # Setup asyncio event loop
    loop = setup_asyncio_event_loop()
    
    # Run in appropriate mode
    try:
        if args.no_gui:
            # Command-line mode
            return loop.run_until_complete(cli_mode(args.task))
        else:
            # GUI mode
            return gui_mode()
    finally:
        # Clean up asyncio event loop
        loop.close()


if __name__ == "__main__":
    sys.exit(main())