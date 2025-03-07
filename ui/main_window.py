import sys
import os
import logging
import asyncio
import threading
from typing import Dict, List, Any, Optional, Callable, Union
from pathlib import Path
from functools import partial

from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                            QLabel, QLineEdit, QPushButton, QTextEdit, QSplitter,
                            QTabWidget, QTreeWidget, QTreeWidgetItem, QProgressBar,
                            QStatusBar, QScrollArea, QFrame, QMessageBox, QFileDialog)
from PyQt6.QtCore import Qt, QSize, QThread, pyqtSignal, pyqtSlot, QMetaObject, Q_ARG, QObject
from PyQt6.QtGui import QIcon, QFont, QColor, QTextCursor, QPixmap

# Local imports
from ui.task_panel import TaskPanel

# Set up logging
logging.basicConfig(level=logging.INFO,
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class UISignals(QObject):
    """Signal class for thread-safe UI updates."""
    add_output = pyqtSignal(str, str)
    update_task_panel_signal = pyqtSignal(object, object, int, object)
    update_status_signal = pyqtSignal(str)
    set_processing_signal = pyqtSignal(bool)
    set_querying_signal = pyqtSignal(bool)


class AsyncWorker(QThread):
    """Worker thread for running async tasks without blocking the UI."""
    
    # Define signals
    finished = pyqtSignal(object)
    error = pyqtSignal(str)
    
    def __init__(self, coro, parent=None):
        """
        Initialize the worker with a coroutine.
        
        Args:
            coro: Coroutine to run asynchronously.
            parent: Parent QObject.
        """
        super().__init__(parent)
        self.coro = coro
        self.loop = None
    
    def run(self):
        """Run the coroutine in a new event loop."""
        try:
            # Create a new event loop for this thread
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
            
            # Run the coroutine and get the result
            result = self.loop.run_until_complete(self.coro)
            
            # Emit the finished signal with the result
            self.finished.emit(result)
            
            # Close the event loop
            self.loop.close()
            self.loop = None
        except Exception as e:
            # Emit the error signal with the exception message
            self.error.emit(str(e))
            if self.loop and not self.loop.is_closed():
                self.loop.close()
                self.loop = None


class OutputLine:
    """Represents a line of output with type information for styling."""
    
    def __init__(self, text: str, output_type: str = 'normal'):
        """
        Initialize an output line.
        
        Args:
            text: The text content of the line.
            output_type: The type of output for styling (normal, user, system, error, result).
        """
        self.text = text
        self.type = output_type


class MainWindow(QMainWindow):
    """Main application window."""
    
    def __init__(self):
        """Initialize the main window."""
        super().__init__()
        
        self.setWindowTitle("AI Desktop Agent")
        self.setGeometry(100, 100, 1200, 800)
        
        # Initialize state
        self.is_processing = False
        self.is_querying = False
        self.output_lines = []
        self.workers = []
        
        # Initialize UI signals
        self.ui_signals = UISignals()
        self.ui_signals.add_output.connect(self.add_output_line)
        self.ui_signals.update_task_panel_signal.connect(self.update_task_panel)
        self.ui_signals.update_status_signal.connect(self.update_status)
        self.ui_signals.set_processing_signal.connect(self.set_processing)
        self.ui_signals.set_querying_signal.connect(self.set_querying)
        
        # Connect to the task manager
        from core.task_manager import task_manager
        self.task_manager = task_manager
        
        # Connect event handlers
        self.setup_event_handlers()
        
        # Set up UI components
        self.setup_ui()
        
        # Add initial welcome message
        self.add_output_line("AI Desktop Agent initialized. How can I help you?", "system")
    
    def closeEvent(self, event):
        """Handle window close event to properly clean up threads."""
        # Check if there are any active workers
        if self.workers:
            # Option 1: Wait for workers to finish (blocks UI)
            for worker in self.workers:
                worker.wait()
            
            # Option 2: Terminate workers (more aggressive)
            # for worker in self.workers:
            #     worker.terminate()
            
            self.workers.clear()
        
        # Call the parent class closeEvent
        super().closeEvent(event)
    
    def setup_event_handlers(self):
        """Set up event handlers for task manager events."""
        # Connect to task manager events
        events = [
            ('analyzing', self.on_task_analyzing),
            ('analyzed', self.on_task_analyzed),
            ('step-started', self.on_step_started),
            ('step-completed', self.on_step_completed),
            ('step-error', self.on_step_error),
            ('completed', self.on_task_completed),
            ('error', self.on_task_error),
            ('calculation-result', self.on_calculation_result),
            ('task-summary', self.on_task_summary)
        ]
        
        # Register event handlers
        for event_name, handler in events:
            self.task_manager.on(event_name, handler)
    
    def setup_ui(self):
        """Set up the user interface."""
        # Create central widget and main layout
        central_widget = QWidget()
        main_layout = QHBoxLayout(central_widget)
        
        # Create splitter for resizable panels
        splitter = QSplitter(Qt.Orientation.Horizontal)
        main_layout.addWidget(splitter)
        
        # Create task panel
        self.task_panel = TaskPanel()
        splitter.addWidget(self.task_panel)
        
        # Create main area
        main_area = QWidget()
        main_area_layout = QVBoxLayout(main_area)
        main_area_layout.setContentsMargins(10, 10, 10, 10)
        splitter.addWidget(main_area)
        
        # Create output area
        self.output_area = QTextEdit()
        self.output_area.setReadOnly(True)
        self.output_area.setFont(QFont('Consolas', 10))
        self.output_area.setStyleSheet("""
            QTextEdit {
                background-color: white;
                border: 1px solid #ddd;
                border-radius: 5px;
                padding: 10px;
            }
        """)
        main_area_layout.addWidget(self.output_area)
        
        # Create input container
        input_container = QWidget()
        input_layout = QVBoxLayout(input_container)
        input_layout.setContentsMargins(0, 10, 0, 0)
        main_area_layout.addWidget(input_container)
        
        # Create input field and buttons
        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("Enter a question or task...")
        self.input_field.setFont(QFont('Segoe UI', 10))
        self.input_field.setStyleSheet("""
            QLineEdit {
                border: 1px solid #ddd;
                border-radius: 5px;
                padding: 10px;
                margin-bottom: 10px;
            }
            QLineEdit:focus {
                border-color: #3498db;
            }
        """)
        input_layout.addWidget(self.input_field)
        
        # Connect input field to submit action
        self.input_field.returnPressed.connect(self.on_submit)
        
        # Create button container
        button_container = QWidget()
        button_layout = QHBoxLayout(button_container)
        button_layout.setContentsMargins(0, 0, 0, 0)
        input_layout.addWidget(button_container)
        
        # Create buttons
        self.ask_button = QPushButton("Just Ask")
        self.ask_button.setStyleSheet("""
            QPushButton {
                background-color: #6c757d;
                color: white;
                border: none;
                border-radius: 5px;
                padding: 10px 20px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #5a6268;
            }
            QPushButton:disabled {
                background-color: #adb5bd;
            }
        """)
        self.ask_button.clicked.connect(self.on_just_ask)
        button_layout.addWidget(self.ask_button)
        
        self.execute_button = QPushButton("Execute")
        self.execute_button.setStyleSheet("""
            QPushButton {
                background-color: #3498db;
                color: white;
                border: none;
                border-radius: 5px;
                padding: 10px 20px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
            QPushButton:disabled {
                background-color: #7fbbe3;
            }
        """)
        self.execute_button.clicked.connect(self.on_submit)
        button_layout.addWidget(self.execute_button)
        
        # Create status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        
        # Add status label
        self.status_label = QLabel("Ready")
        self.status_bar.addWidget(self.status_label)
        
        # Add version label to right side
        version_label = QLabel("AI Desktop Agent v1.0")
        self.status_bar.addPermanentWidget(version_label)
        
        # Set central widget
        self.setCentralWidget(central_widget)
        
        # Set splitter sizes for good initial layout (30% task panel, 70% main area)
        splitter.setSizes([300, 700])
    
    def set_processing(self, state):
        """Set processing state and update UI."""
        self.is_processing = state
        self.update_ui_state()

    def set_querying(self, state):
        """Set querying state and update UI."""
        self.is_querying = state
        self.update_ui_state()
    
    def add_output_line(self, text: str, line_type: str = 'normal'):
        """
        Add a line to the output area with appropriate formatting.
        
        Args:
            text: The text to add.
            line_type: The type of line for styling (normal, user, system, error, result).
        """
        # Store line in history
        self.output_lines.append(OutputLine(text, line_type))
        
        # Clear and rebuild output
        self.refresh_output()
    
    def refresh_output(self):
        """Refresh the output area with all stored lines."""
        self.output_area.clear()
        
        for line in self.output_lines:
            # Set text color based on line type
            if line.type == 'user':
                self.output_area.setTextColor(QColor('#2980b9'))
                self.output_area.setFontWeight(QFont.Weight.Bold)
            elif line.type == 'system':
                self.output_area.setTextColor(QColor('#27ae60'))
                self.output_area.setFontWeight(QFont.Weight.Normal)
            elif line.type == 'error':
                self.output_area.setTextColor(QColor('#e74c3c'))
                self.output_area.setFontWeight(QFont.Weight.Normal)
            elif line.type == 'result':
                self.output_area.setTextColor(QColor('#9b59b6'))
                self.output_area.setFontWeight(QFont.Weight.Bold)
            elif line.type == 'ai-response':
                self.output_area.setTextColor(QColor('#2c3e50'))
                self.output_area.setFontWeight(QFont.Weight.Normal)
                # Insert in a block with background color
                cursor = self.output_area.textCursor()
                cursor.movePosition(QTextCursor.MoveOperation.End)
                
                # Create a frame-like background
                self.output_area.append('')  # Add empty line before
                cursor = self.output_area.textCursor()
                cursor.movePosition(QTextCursor.MoveOperation.End)
                
                format = cursor.blockFormat()
                format.setBackground(QColor('#ecf0f1'))
                format.setLeftMargin(10)
                format.setRightMargin(10)
                format.setTopMargin(5)
                format.setBottomMargin(5)
                cursor.setBlockFormat(format)
                
                self.output_area.setTextCursor(cursor)
                self.output_area.insertPlainText(line.text)
                
                # Add a line after the block too
                self.output_area.append('')
                continue  # Skip the normal append
            else:
                self.output_area.setTextColor(QColor('#2c3e50'))
                self.output_area.setFontWeight(QFont.Weight.Normal)
            
            # Append the text
            self.output_area.append(line.text)
        
        # Scroll to the bottom
        self.output_area.moveCursor(QTextCursor.MoveOperation.End)
    
    def update_status(self, message: str):
        """
        Update the status bar message.
        
        Args:
            message: The status message to display.
        """
        self.status_label.setText(message)
    
    def update_task_panel(self, task: Optional[str] = None, steps: Optional[List] = None, 
                         current_step: int = -1, analysis: Optional[str] = None):
        """
        Update the task panel with current task information.
        
        Args:
            task: The current task description.
            steps: List of task steps.
            current_step: Index of the current step.
            analysis: Task analysis text.
        """
        self.task_panel.update_task(task, steps, current_step, analysis)
    
    async def handle_agent_info_query(self, query):
        """
        Handle queries about the agent itself.
        
        Args:
            query: The user's query about the agent.
            
        Returns:
            Dict with agent information.
        """
        from utils.deepseek_client import DeepseekClient
        client = DeepseekClient()
        
        # Get agent info response
        response = await client.generate_json(query)
        
        # Send to UI thread
        self.ui_signals.add_output.emit(response.get('analysis', 'I am an AI Desktop Agent designed to help automate tasks on your computer.'), 'ai-response')
        
        # This is only analysis, not execution, so don't update task panel
        return response
    
    async def execute_with_analysis(self, task):
        """
        Ensure task is analyzed before executing it.
        
        Args:
            task: The task to analyze and execute.
            
        Returns:
            Task execution result.
        """
        try:
            # First analyze the task
            analysis_result = await self.task_manager.analyze_task(task)
            
            # Check if this is an info-type response that doesn't need execution
            if (isinstance(analysis_result, dict) and 
                analysis_result.get('isAgentInfoResponse', False)):
                # For agent info, we don't need to execute anything
                return {
                    'success': True,
                    'message': 'Information provided',
                    'context': {'task_description': task}
                }
            
            # Then try to execute it
            try:
                execution_result = await self.task_manager.execute_full_task()
                return execution_result
            except Exception as execution_error:
                self.logger.error(f"Task execution error: {str(execution_error)}")
                self.ui_signals.add_output.emit(f"Task execution failed: {str(execution_error)}", 'error')
                
                # Return structured error
                return {
                    'success': False,
                    'error': str(execution_error),
                    'analysis': analysis_result.get('analysis', ''),
                    'context': {'task_description': task}
                }
        except Exception as error:
            self.logger.error(f"Error in execute_with_analysis: {str(error)}")
            
            # Signal the error through UI
            self.ui_signals.add_output.emit(f"Error analyzing and executing task: {str(error)}", 'error')
            
            # Return structured error response
            return {
                'success': False,
                'error': str(error),
                'context': {'task_description': task}
            }
        
    def on_submit(self):
        """Handle submit button click to execute a task."""
        command = self.input_field.text().strip()
        
        if not command or self.is_processing or self.is_querying:
            return
        
        # Add user command to output
        self.add_output_line(command, 'user')
        
        # Start task processing
        self.is_processing = True
        self.update_status("Executing task...")
        self.update_ui_state()
        
        # Check for agent info question - handle differently
        from utils.deepseek_client import DeepseekClient
        client = DeepseekClient()
        if client.is_agent_info_query(command):
            # For info queries, we should ONLY do analysis, not execution
            worker = AsyncWorker(self.handle_agent_info_query(command))
            worker.finished.connect(lambda result: self.ui_signals.set_processing_signal.emit(False))
            worker.finished.connect(lambda result: self.workers.remove(worker) if worker in self.workers else None)
            worker.error.connect(lambda error: self.workers.remove(worker) if worker in self.workers else None)
            self.workers.append(worker)
            worker.start()
        else:
            # Only execute regular tasks, not info queries
            worker = AsyncWorker(self.execute_with_analysis(command))
            worker.finished.connect(self.on_task_execution_complete)
            worker.error.connect(self.on_task_execution_error)
            worker.finished.connect(lambda result: self.workers.remove(worker) if worker in self.workers else None)
            worker.error.connect(lambda error: self.workers.remove(worker) if worker in self.workers else None)
            self.workers.append(worker)
            worker.start()
        
        # Clear input field
        self.input_field.clear()
    
    def on_just_ask(self):
        """Handle just ask button click to analyze without executing."""
        command = self.input_field.text().strip()
        
        if not command or self.is_processing or self.is_querying:
            return
        
        # Add user command to output
        self.add_output_line(command, 'user')
        
        # Start query processing
        self.is_querying = True
        self.update_status("Processing question...")
        self.update_ui_state()
        
        # Check for agent info question
        from utils.deepseek_client import DeepseekClient
        client = DeepseekClient()
        if client.is_agent_info_query(command):
            # Handle agent info query directly
            worker = AsyncWorker(self.handle_agent_info_query(command))
        else:
            # Normal task analysis
            worker = AsyncWorker(self.task_manager.analyze_task(command))
        
        worker.finished.connect(self.on_task_analysis_complete)
        worker.error.connect(self.on_task_analysis_error)
        worker.finished.connect(lambda result: self.workers.remove(worker) if worker in self.workers else None)
        worker.error.connect(lambda error: self.workers.remove(worker) if worker in self.workers else None)
        self.workers.append(worker)
        worker.start()
        
        # Clear input field
        self.input_field.clear()
    
    def update_ui_state(self):
        """Update UI based on current processing state."""
        is_busy = self.is_processing or self.is_querying
        
        # Update input field and buttons
        self.input_field.setEnabled(not is_busy)
        self.ask_button.setEnabled(not is_busy)
        self.execute_button.setEnabled(not is_busy)
        
        # Update status label
        if self.is_processing:
            self.update_status("Executing task...")
        elif self.is_querying:
            self.update_status("Processing question...")
        else:
            self.update_status("Ready")
    
    # Event handlers for task manager events - updated for thread safety
    def on_task_analyzing(self, data):
        """Handle task analyzing event."""
        task = data.get('task', '')
        self.ui_signals.add_output.emit(f"Analyzing task: {task}", 'system')
    
    def on_task_analyzed(self, data):
        """Handle task analyzed event."""
        task = data.get('task', '')
        steps = data.get('steps', [])
        analysis = data.get('analysis', '')
        
        # Update task panel via signal
        self.ui_signals.update_task_panel_signal.emit(task, steps, -1, analysis)
        
        # Add analysis to output as AI response
        self.ui_signals.add_output.emit(analysis, 'ai-response')
        
        # If this was just a query (not execution), we can stop processing
        if self.is_querying and not self.is_processing:
            self.ui_signals.set_querying_signal.emit(False)
    
    def on_step_started(self, data):
        """Handle step started event."""
        step = data.get('step', {})
        index = data.get('index', 0)
        total = data.get('total', len(self.task_panel.steps))
        
        step_name = step.get('name', '') or step.get('description', 'Unknown step')
        self.ui_signals.add_output.emit(f"Starting step {index + 1}/{total}: {step_name}", 'system')
        
        # Update task panel via signal
        self.ui_signals.update_task_panel_signal.emit(
            self.task_panel.task,
            self.task_panel.steps,
            index,
            self.task_panel.analysis
        )
    
    def on_step_completed(self, data):
        """Handle step completed event."""
        step = data.get('step', {})
        index = data.get('index', 0)
        
        step_name = step.get('name', '') or step.get('description', 'Unknown step')
        self.ui_signals.add_output.emit(f"Completed step {index + 1}: {step_name}", 'system')
    
    def on_step_error(self, data):
        """Handle step error event."""
        error = data.get('error', '')
        index = data.get('index', 0)
        
        self.ui_signals.add_output.emit(f"Error in step {index + 1}: {error}", 'error')
    
    def on_task_completed(self, data):
        """Handle task completed event."""
        self.ui_signals.add_output.emit("Task completed successfully.", 'system')
        self.ui_signals.set_processing_signal.emit(False)
        self.ui_signals.set_querying_signal.emit(False)
    
    def on_task_error(self, data):
        """Handle task error event."""
        error = data.get('error', '')
        
        self.ui_signals.add_output.emit(f"Error: {error}", 'error')
        self.ui_signals.set_processing_signal.emit(False)
        self.ui_signals.set_querying_signal.emit(False)
    
    def on_calculation_result(self, data):
        """Handle calculation result event."""
        operation = data.get('operation', '')
        result = data.get('result', '')
        
        self.ui_signals.add_output.emit(f"Result: {operation} = {result}", 'result')
    
    def on_task_summary(self, data):
        """Handle task summary event."""
        message = data.get('message', '')
        results = data.get('results', {})
        
        if results.get('calculation'):
            calculation = results.get('calculation', {})
            self.ui_signals.add_output.emit(f"The answer is: {calculation.get('result', '')}", 'result')
        
        self.ui_signals.add_output.emit(message, 'system')
        self.ui_signals.set_processing_signal.emit(False)
        self.ui_signals.set_querying_signal.emit(False)
    
    # Callback handlers for AsyncWorker
    def on_task_execution_complete(self, result):
        """Handle task execution completion."""
        success = result.get('success', False)
        
        if not success:
            error = result.get('error', 'Unknown error')
            self.ui_signals.add_output.emit(f"Task execution failed: {error}", 'error')
        else:
            # For successful agent info queries, we've already shown the response,
            # so no need to show anything extra here
            pass
        
        self.ui_signals.set_processing_signal.emit(False)
        
    def on_task_execution_error(self, error_message):
        """Handle task execution error."""
        self.ui_signals.add_output.emit(f"Error executing task: {error_message}", 'error')
        self.ui_signals.set_processing_signal.emit(False)
    
    def on_task_analysis_complete(self, result):
        """Handle task analysis completion."""
        # Analysis results are already handled by on_task_analyzed event
        self.ui_signals.set_querying_signal.emit(False)
    
    def on_task_analysis_error(self, error_message):
        """Handle task analysis error."""
        self.ui_signals.add_output.emit(f"Error analyzing task: {error_message}", 'error')
        self.ui_signals.set_querying_signal.emit(False)


def run_app():
    """Run the application."""
    app = QApplication(sys.argv)
    
    # Set application style
    app.setStyle("Fusion")
    
    # Create and show main window
    window = MainWindow()
    window.show()
    
    # Start the event loop
    sys.exit(app.exec())


if __name__ == "__main__":
    run_app()