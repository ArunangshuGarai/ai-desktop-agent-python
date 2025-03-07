import sys
from typing import Dict, List, Any, Optional

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QScrollArea,
                            QFrame, QSizePolicy, QStackedWidget, QProgressBar)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QFont, QColor, QPalette


class StepItem(QFrame):
    """A widget representing a single step in the task panel."""
    
    def __init__(self, step: Dict[str, Any], index: int, status: str = 'pending'):
        """
        Initialize a step item.
        
        Args:
            step: Dictionary containing step information.
            index: Step index (0-based).
            status: Step status ('pending', 'active', 'completed').
        """
        super().__init__()
        
        # Store step data
        self.step = step
        self.index = index
        self.status = status
        
        # Set up UI
        self.setup_ui()
    
    def setup_ui(self):
        """Set up the UI for a step item."""
        # Set frame style based on status
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setFrameShadow(QFrame.Shadow.Raised)
        self.setLineWidth(1)
        
        # Set background color based on status
        palette = self.palette()
        if self.status == 'active':
            bg_color = QColor('#3498db')
            border_color = QColor('#2980b9')
        elif self.status == 'completed':
            bg_color = QColor('#27ae60')
            border_color = QColor('#219653')
        else:
            bg_color = QColor('#34495e')
            border_color = QColor('#2c3e50')
        
        palette.setColor(QPalette.ColorRole.Window, bg_color)
        palette.setColor(QPalette.ColorRole.WindowText, Qt.GlobalColor.white)
        self.setPalette(palette)
        self.setAutoFillBackground(True)
        
        # Create layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        
        # Create header layout
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 8)
        layout.addLayout(header_layout)
        
        # Step number circle
        step_number = QLabel(str(self.index + 1))
        step_number.setFixedSize(24, 24)
        step_number.setAlignment(Qt.AlignmentFlag.AlignCenter)
        step_number.setStyleSheet(f"""
            background-color: rgba(255, 255, 255, 0.2);
            border-radius: 12px;
            color: white;
            font-size: 12px;
        """)
        header_layout.addWidget(step_number)
        
        # Step name
        step_name = QLabel(self.step.get('name', '') or self.step.get('description', 'Unknown step'))
        step_name.setFont(QFont('Segoe UI', 10, QFont.Weight.Bold))
        step_name.setStyleSheet("color: white;")
        header_layout.addWidget(step_name, 1)  # 1 = stretch factor
        
        # Step type badge
        step_type = self.step.get('type', '')
        if step_type:
            type_label = QLabel(step_type.upper())
            type_label.setStyleSheet("""
                background-color: rgba(255, 255, 255, 0.2);
                border-radius: 3px;
                padding: 2px 6px;
                color: white;
                font-size: 10px;
            """)
            header_layout.addWidget(type_label)
        
        # Step description
        description = self.step.get('description', '')
        if description and description != step_name.text():
            desc_label = QLabel(description)
            desc_label.setStyleSheet("color: white; margin-left: 34px;")
            desc_label.setWordWrap(True)
            layout.addWidget(desc_label)
        
        # Actions container
        actions = self.step.get('actions', [])
        if actions:
            actions_container = QFrame()
            actions_container.setStyleSheet("""
                background-color: rgba(255, 255, 255, 0.1);
                border-radius: 3px;
                margin-left: 34px;
                padding: 5px;
            """)
            actions_layout = QVBoxLayout(actions_container)
            actions_layout.setContentsMargins(5, 5, 5, 5)
            actions_layout.setSpacing(5)
            
            for action in actions:
                action_text = f"{action.get('action', 'unknown')}"
                params = action.get('params', {})
                if params:
                    param_str = str(params)
                    if len(param_str) > 30:
                        param_str = param_str[:27] + "..."
                    action_text += f": {param_str}"
                
                action_label = QLabel(action_text)
                action_label.setStyleSheet("color: white; font-size: 11px;")
                action_label.setWordWrap(True)
                actions_layout.addWidget(action_label)
            
            layout.addWidget(actions_container)
        
        # Set border style
        self.setStyleSheet(f"""
            StepItem {{
                border-left: 4px solid {border_color.name()};
                border-radius: 5px;
            }}
        """)


class TaskPanel(QWidget):
    """A panel displaying the current task and its steps."""
    
    def __init__(self):
        """Initialize the task panel."""
        super().__init__()
        
        # Initialize state
        self.task = None
        self.steps = []
        self.current_step = -1
        self.analysis = ""
        
        # Set up UI
        self.setup_ui()
    
    def setup_ui(self):
        """Set up the UI for the task panel."""
        # Set background color
        self.setStyleSheet("""
            TaskPanel {
                background-color: #2c3e50;
                color: white;
            }
        """)
        
        # Create main layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Create header
        self.header = QFrame()
        self.header.setStyleSheet("""
            QFrame {
                background-color: #1a2533;
                border-bottom: 1px solid #34495e;
                padding: 15px;
            }
        """)
        header_layout = QVBoxLayout(self.header)
        header_layout.setContentsMargins(15, 15, 15, 15)
        
        # Title label
        self.title_label = QLabel("AI Desktop Agent")
        self.title_label.setFont(QFont('Segoe UI', 12, QFont.Weight.Bold))
        self.title_label.setStyleSheet("color: white;")
        header_layout.addWidget(self.title_label)
        
        # Subtitle label
        self.subtitle_label = QLabel("Waiting for instructions...")
        self.subtitle_label.setFont(QFont('Segoe UI', 9))
        self.subtitle_label.setStyleSheet("color: rgba(255, 255, 255, 0.8); margin-top: 5px;")
        header_layout.addWidget(self.subtitle_label)
        
        layout.addWidget(self.header)
        
        # Create content stacked widget
        self.content_stack = QStackedWidget()
        layout.addWidget(self.content_stack, 1)  # 1 = stretch factor
        
        # Create empty state widget
        self.empty_state = QWidget()
        self.empty_state.setStyleSheet("""
            QWidget {
                background-color: #2c3e50;
            }
        """)
        empty_layout = QVBoxLayout(self.empty_state)
        empty_layout.setContentsMargins(20, 40, 20, 40)
        empty_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        empty_message = QLabel("No active task")
        empty_message.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_message.setStyleSheet("color: rgba(255, 255, 255, 0.7); font-size: 14px;")
        empty_layout.addWidget(empty_message)
        
        empty_submessage = QLabel("Enter a command to get started")
        empty_submessage.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_submessage.setStyleSheet("color: rgba(255, 255, 255, 0.5); font-size: 12px;")
        empty_layout.addWidget(empty_submessage)
        
        self.content_stack.addWidget(self.empty_state)
        
        # Create task content widget with scroll area
        self.task_content = QWidget()
        self.task_content.setStyleSheet("""
            QWidget {
                background-color: #2c3e50;
            }
        """)
        
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setWidget(self.task_content)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        
        task_layout = QVBoxLayout(self.task_content)
        task_layout.setContentsMargins(15, 15, 15, 15)
        task_layout.setSpacing(15)
        
        # Analysis section
        self.analysis_frame = QFrame()
        self.analysis_frame.setStyleSheet("""
            QFrame {
                background-color: #34495e;
                border-radius: 5px;
                padding: 15px;
            }
        """)
        analysis_layout = QVBoxLayout(self.analysis_frame)
        analysis_layout.setContentsMargins(15, 15, 15, 15)
        
        analysis_title = QLabel("Task Analysis")
        analysis_title.setFont(QFont('Segoe UI', 10, QFont.Weight.Bold))
        analysis_title.setStyleSheet("color: white; margin-bottom: 10px;")
        analysis_layout.addWidget(analysis_title)
        
        self.analysis_text = QLabel("No analysis available")
        self.analysis_text.setWordWrap(True)
        self.analysis_text.setStyleSheet("color: white; line-height: 140%;")
        self.analysis_text.setTextFormat(Qt.TextFormat.RichText)
        analysis_layout.addWidget(self.analysis_text)
        
        task_layout.addWidget(self.analysis_frame)
        
        # Steps section
        steps_container = QWidget()
        steps_layout = QVBoxLayout(steps_container)
        steps_layout.setContentsMargins(0, 0, 0, 0)
        steps_layout.setSpacing(15)
        
        # Steps title
        self.steps_title = QLabel("Steps (0/0)")
        self.steps_title.setFont(QFont('Segoe UI', 10, QFont.Weight.Bold))
        self.steps_title.setStyleSheet("color: white;")
        steps_layout.addWidget(self.steps_title)
        
        # Steps list
        self.steps_list = QVBoxLayout()
        self.steps_list.setContentsMargins(0, 0, 0, 0)
        self.steps_list.setSpacing(10)
        steps_layout.addLayout(self.steps_list)
        
        task_layout.addWidget(steps_container)
        task_layout.addStretch(1)  # Add stretch at the end to push content up
        
        self.content_stack.addWidget(self.scroll_area)
        
        # Start with empty state
        self.content_stack.setCurrentWidget(self.empty_state)
        
        # Set minimum size
        self.setMinimumWidth(280)
    
    def update_task(self, task: Optional[str] = None, steps: Optional[List] = None, 
                   current_step: int = -1, analysis: Optional[str] = None):
        """
        Update the task panel with new task information.
        
        Args:
            task: The task description.
            steps: List of steps in the task.
            current_step: Current step index (0-based).
            analysis: Task analysis text.
        """
        # Update internal state
        self.task = task
        self.steps = steps or []
        self.current_step = current_step
        if analysis is not None:
            self.analysis = analysis
        
        # Clear previous steps
        while self.steps_list.count():
            item = self.steps_list.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        
        # Update UI based on whether there's a task
        if task and self.steps:
            # Update subtitle
            self.subtitle_label.setText("Task in Progress")
            
            # Update analysis
            self.analysis_text.setText(self.analysis)
            
            # Update steps title
            self.steps_title.setText(f"Steps ({current_step + 1}/{len(self.steps)})")
            
            # Add step items
            for i, step in enumerate(self.steps):
                # Determine step status
                status = 'pending'
                if i == current_step:
                    status = 'active'
                elif i < current_step:
                    status = 'completed'
                
                # Create and add step item
                step_item = StepItem(step, i, status)
                self.steps_list.addWidget(step_item)
            
            # Show task content
            self.content_stack.setCurrentWidget(self.scroll_area)
        else:
            # Update subtitle
            self.subtitle_label.setText("Waiting for instructions...")
            
            # Show empty state
            self.content_stack.setCurrentWidget(self.empty_state)