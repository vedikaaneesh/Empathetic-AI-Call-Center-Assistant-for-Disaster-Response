import sys
import subprocess
import os
import requests
from io import BytesIO
from PIL import Image
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                           QHBoxLayout, QPushButton, QLabel, QTreeWidget, 
                           QTreeWidgetItem, QMessageBox, QTextEdit, QSplitter,
                           QStackedWidget, QLineEdit, QFrame, QGridLayout,
                           QComboBox, QListWidget, QListWidgetItem, QDialog,
                           QGraphicsDropShadowEffect)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer, QUrl, QSize
from PyQt5.QtGui import QFont, QPainter, QPixmap, QColor
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtChart import (QChart, QChartView, QPieSeries, QBarSeries,
                          QBarSet, QBarCategoryAxis, QValueAxis, QLineSeries, QDateTimeAxis)
import sqlite3
import signal
from datetime import datetime
from collections import Counter
import hashlib  # For password hashing
from PyQt5.QtCore import QDateTime

class ConversationThread(QThread):
    finished = pyqtSignal()
    error = pyqtSignal(str)
    
    def __init__(self):
        super().__init__()
        self.process = None
        self.termination_requested = False
        self.max_wait_time = 30  # Maximum time to wait for summary completion in seconds
        self.wait_start_time = None

    def run(self):
        try:
            if os.path.exists("summary_complete.txt"):
                os.remove("summary_complete.txt")
            if os.path.exists("end_call.txt"):
                os.remove("end_call.txt")
                
            self.process = subprocess.Popen([sys.executable, 'main.py'], 
                                    stdout=subprocess.PIPE, 
                                    stderr=subprocess.PIPE,
                                    universal_newlines=True)
            
            # Read output in real-time
            while True:
                if self.process.poll() is not None:
                    break
                    
                output = self.process.stdout.readline()
                if output:
                    print(output.strip())
                    
            stdout, stderr = self.process.communicate()
            
            if self.process.returncode != 0 and not self.process.returncode == -signal.SIGTERM:
                print(f"Process error output: {stderr}")
                self.error.emit(f"Error in main.py: {stderr}")
            else:
                print("Process completed successfully")
                self.finished.emit()
        except Exception as e:
            print(f"Thread error: {str(e)}")
            self.error.emit(str(e))

    def stop_conversation(self):
        if self.process:
            print("Stopping conversation...")
            # Create end call signal first
            with open("end_call.txt", "w") as f:
                f.write("1")
            print("Created end_call.txt signal")
            
            # Process the conversation immediately
            try:
                print("Processing conversation immediately...")
                with open("conversations.txt", "r") as f:
                    conversations = f.read()
                    print("Final conversation length:", len(conversations))
                
                if conversations.strip():
                    # Import and call get_conversation directly
                    from main import get_conversation
                    get_conversation()
                    print("Successfully processed conversation")
                else:
                    print("Warning: Empty conversation, skipping processing")
            except Exception as e:
                print(f"Error processing conversation: {e}")
            
            # Force stop the process after processing
            QTimer.singleShot(1000, self.force_stop_if_needed)
            
    def force_stop_if_needed(self):
        if self.process and self.process.poll() is None:
            print("Process still running, forcing termination...")
            try:
                self.process.terminate()
                # Give it a moment to terminate gracefully
                QTimer.singleShot(1000, self.kill_if_needed)
            except Exception as e:
                print(f"Error terminating process: {e}")
                self.kill_if_needed()
    
    def kill_if_needed(self):
        if self.process and self.process.poll() is None:
            print("Process still running after terminate, killing...")
            try:
                self.process.kill()
            except Exception as e:
                print(f"Error killing process: {e}")
            finally:
                self.finished.emit()
            
class VoiceAnalysisUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.dark_mode = False  # Track dark mode state
        self.setWindowTitle("Emergency Call Center Assistant")
        self.setGeometry(100, 100, 1400, 900)
        
        # Create central widget and main layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Create navigation bar
        nav_bar = QWidget()
        nav_bar.setStyleSheet("""
            QWidget {
                background-color: #f8f9fa;
                border-bottom: 1px solid #dee2e6;
            }
            QPushButton {
                background-color: transparent;
                border: none;
                padding: 15px 25px;
                font-size: 14px;
                color: #6c757d;
            }
            QPushButton:hover {
                color: #007bff;
            }
            QPushButton:checked {
                color: #007bff;
                border-bottom: 2px solid #007bff;
                font-weight: bold;
            }
        """)
        nav_layout = QHBoxLayout(nav_bar)
        nav_layout.setContentsMargins(20, 0, 20, 0)
        
        # Create navigation buttons
        self.active_calls_btn = QPushButton("Active Calls")
        self.active_calls_btn.setCheckable(True)
        self.call_history_btn = QPushButton("Call History")
        self.call_history_btn.setCheckable(True)
        self.analytics_btn = QPushButton("Analytics")
        self.analytics_btn.setCheckable(True)
        self.settings_btn = QPushButton("Settings")
        self.settings_btn.setCheckable(True)
        
        # Add buttons to navigation
        nav_layout.addWidget(self.active_calls_btn)
        nav_layout.addWidget(self.call_history_btn)
        nav_layout.addWidget(self.analytics_btn)
        nav_layout.addWidget(self.settings_btn)
        nav_layout.addStretch()
        
        # Create stacked widget for different pages
        self.stacked_widget = QStackedWidget()
        
        # Create pages
        self.active_calls_page = self.create_active_calls_page()
        self.call_history_page = self.create_call_history_page()
        self.analytics_page = self.create_analytics_page()
        self.settings_page = self.create_settings_page()  # New settings page
        
        # Add pages to stacked widget
        self.stacked_widget.addWidget(self.active_calls_page)
        self.stacked_widget.addWidget(self.call_history_page)
        self.stacked_widget.addWidget(self.analytics_page)
        self.stacked_widget.addWidget(self.settings_page)
        
        # Connect button signals
        self.active_calls_btn.clicked.connect(lambda: self.switch_page(0))
        self.call_history_btn.clicked.connect(lambda: self.switch_page(1))
        self.analytics_btn.clicked.connect(lambda: self.switch_page(2))
        self.settings_btn.clicked.connect(lambda: self.switch_page(3))
        
        # Add widgets to main layout
        layout.addWidget(nav_bar)
        layout.addWidget(self.stacked_widget)
        
        # Initialize thread and timers
        self.conv_thread = None
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_transcript)
        
        self.summary_check_timer = QTimer()
        self.summary_check_timer.timeout.connect(self.check_summary_completion)
        self.summary_check_timer.start(1000)  # Check every second
        
        # Set initial page
        self.switch_page(0)
        
        # Load conversations when the application starts
        QTimer.singleShot(100, self.update_conversation_list)  # Use QTimer to ensure UI is fully initialized
        # Initialize analytics with real data
        QTimer.singleShot(500, self.update_analytics)
        
    def create_active_calls_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Control buttons
        button_layout = QHBoxLayout()
        
        self.start_button = QPushButton("Start Conversation")
        self.start_button.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:disabled {
                background-color: #cccccc;
            }
        """)
        self.start_button.clicked.connect(self.start_conversation_thread)
        button_layout.addWidget(self.start_button)
        
        self.end_button = QPushButton("End Call")
        self.end_button.setStyleSheet("""
            QPushButton {
                background-color: #ff9800;
                color: white;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #f57c00;
            }
            QPushButton:disabled {
                background-color: #cccccc;
            }
        """)
        self.end_button.clicked.connect(self.end_conversation)
        self.end_button.setEnabled(False)
        button_layout.addWidget(self.end_button)
        
        # Add Dispatch button and options
        self.dispatch_button = QPushButton("Dispatch")
        self.dispatch_button.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
            QPushButton:disabled {
                background-color: #cccccc;
            }
        """)
        self.dispatch_button.clicked.connect(self.show_dispatch_options)
        button_layout.addWidget(self.dispatch_button)

        # Add Mark as Resolved button
        self.resolve_button = QPushButton("Mark as Resolved")
        self.resolve_button.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:disabled {
                background-color: #cccccc;
            }
        """)
        self.resolve_button.clicked.connect(self.mark_as_resolved)
        button_layout.addWidget(self.resolve_button)

        # Create dispatch options container
        self.dispatch_options = QWidget()
        self.dispatch_options.setFixedHeight(44)
        dispatch_options_layout = QHBoxLayout(self.dispatch_options)
        dispatch_options_layout.setContentsMargins(0, 0, 0, 0)
        dispatch_options_layout.setSpacing(10)
        
        # Create styled service buttons with icons and labels
        self.police_button = QPushButton("🚓 Police")
        self.fire_button = QPushButton("🚒 Firefighters")
        self.medic_button = QPushButton("🚑 Paramedics")
        
        service_buttons = [self.police_button, self.fire_button, self.medic_button]
        
        for button in service_buttons:
            button.setStyleSheet("""
                QPushButton {
                    background-color: #ffffff;
                    color: #333333;
                    padding: 8px 12px;
                    border: 1px solid #dddddd;
                    border-radius: 4px;
                    font-weight: bold;
                    min-width: 120px;
                    text-align: left;
                }
                QPushButton:hover {
                    background-color: #e3f2fd;
                    border-color: #2196F3;
                    color: #2196F3;
                }
                QPushButton:pressed {
                    background-color: #bbdefb;
                }
            """)
            dispatch_options_layout.addWidget(button)
        
        # Connect signals
        self.police_button.clicked.connect(lambda: self.handle_dispatch_button("Police"))
        self.fire_button.clicked.connect(lambda: self.handle_dispatch_button("Firefighters"))
        self.medic_button.clicked.connect(lambda: self.handle_dispatch_button("Paramedics"))
        
        # Hide options initially
        self.dispatch_options.hide()
        
        button_layout.addWidget(self.dispatch_options)
        button_layout.addStretch()
        layout.addLayout(button_layout)
        
        # Create top section splitter (Active Calls, Map, Transcript)
        top_splitter = QSplitter(Qt.Horizontal)
        
        # Left side - Active Calls Stack
        active_calls_widget = QWidget()
        active_calls_layout = QVBoxLayout(active_calls_widget)
        
        active_calls_label = QLabel("Active Emergency Calls")
        active_calls_label.setFont(QFont("Arial", 14, QFont.Bold))
        active_calls_label.setStyleSheet("color: #2196F3; margin-bottom: 5px;")
        active_calls_layout.addWidget(active_calls_label)
        
        # Active calls list using QListWidget
        self.active_calls_list = QListWidget()
        self.active_calls_list.setStyleSheet("""
            QListWidget {
                background-color: #f5f5f5;
                border: 1px solid #ddd;
                border-radius: 8px;
                padding: 5px;
            }
            QListWidget::item {
                background-color: white;
                border: 1px solid #e0e0e0;
                border-radius: 8px;
                padding: 1px;
                margin-bottom: 4px;
            }
            QListWidget::item:selected {
                background-color: #e3f2fd;
                border: 1px solid #2196F3;
            }
            QListWidget::item:hover {
                background-color: #f8f9fa;
            }
        """)
        self.active_calls_list.itemClicked.connect(self.on_active_call_clicked)
        active_calls_layout.addWidget(self.active_calls_list)
        
        # Middle - Map
        map_widget = QWidget()
        map_layout = QVBoxLayout(map_widget)
        
        map_label = QLabel("Location Map")
        map_label.setFont(QFont("Arial", 12, QFont.Bold))
        map_label.setStyleSheet("color: #2196F3; margin-bottom: 3.5px;")
        map_layout.addWidget(map_label)
        
        self.map_view = QWebEngineView()
        self.map_view.setMinimumWidth(400)
        self.map_view.setMinimumHeight(300)
        html_content = """
        <html>
        <head>
            <style>
                body { margin: 0; padding: 0; }
                iframe { width: 100%; height: 100%; border: none; }
            </style>
        </head>
        <body>
            <iframe
                src="https://www.google.com/maps/embed/v1/place?key=AIzaSyCR0nJhZTRbPgKn_r1tUqoQEN1JHAMcx3Q&q=United+States"
                allowfullscreen>
            </iframe>
        </body>
        </html>
        """
        self.map_view.setHtml(html_content)
        map_layout.addWidget(self.map_view)
        
        # Right side - Live Transcript
        transcript_widget = QWidget()
        transcript_layout = QVBoxLayout(transcript_widget)
        
        transcript_label = QLabel("Live Transcript")
        transcript_label.setFont(QFont("Arial", 12, QFont.Bold))
        transcript_label.setStyleSheet("color: #2196F3; margin-bottom: 2px;")
        transcript_layout.addWidget(transcript_label)
        
        # Create a styled transcript area with custom HTML display
        self.transcript_area = QTextEdit()
        self.transcript_area.setReadOnly(True)
        self.transcript_area.setMinimumHeight(300)
        self.transcript_area.setStyleSheet("""
            QTextEdit {
                background-color: #f5f5f5;
                border: 1px solid #ddd;
                border-radius: 4px;
                padding: 5px;
                font-family: Arial;
                font-size: 12px;
            }
        """)
        
        # Set up basic HTML structure for chat-like display
        self.transcript_area.setHtml("""
            <html>
            <head>
                <style>
                    body { 
                        background-color: #f5f5f5; 
                        font-family: Arial, sans-serif;
                        margin: 0;
                        padding: 5px;
                    }
                    .chat-container {
                        display: flex;
                        flex-direction: column;
                        gap: 10px;
                    }
                    .operator-message, .caller-message {
                        max-width: 80%;
                        padding: 10px 14px;
                        border-radius: 18px;
                        margin: 2px 0;
                        position: relative;
                        display: inline-block;
                    }
                    .operator-message {
                        background-color: #e9e9e9;
                        color: #333;
                        align-self: flex-start;
                        margin-right: auto;
                        border-bottom-left-radius: 5px;
                    }
                    .caller-message {
                        background-color: #2979FF;
                        color: white;
                        align-self: flex-end;
                        margin-left: auto;
                        border-bottom-right-radius: 5px;
                    }
                    .operator-icon, .caller-icon {
                        width: 28px;
                        height: 28px;
                        background-color: #ccc;
                        border-radius: 50%;
                        display: inline-flex;
                        align-items: center;
                        justify-content: center;
                        margin-right: 8px;
                        vertical-align: top;
                        text-align: center;
                        font-size: 14px;
                    }
                    .operator-icon {
                        background-color: #e0e0e0;
                    }
                    .caller-icon {
                        background-color: #e0e0e0;
                        margin-right: 0;
                        margin-left: 8px;
                    }
                    .message-row {
                        display: flex;
                        margin-bottom: 12px;
                        align-items: flex-start;
                    }
                    .operator-row {
                        justify-content: flex-start;
                    }
                    .caller-row {
                        justify-content: flex-end;
                        flex-direction: row-reverse;
                    }
                </style>
            </head>
            <body>
                <div class="chat-container">
                    <h3 style="color: #333; border-bottom: 1px solid #ddd; padding-bottom: 5px; margin-top: 0;">CALL TRANSCRIPT</h3>
                </div>
            </body>
            </html>
        """)
        
        transcript_layout.addWidget(self.transcript_area)
        
        # Add all sections to top splitter
        top_splitter.addWidget(active_calls_widget)
        top_splitter.addWidget(map_widget)
        top_splitter.addWidget(transcript_widget)
        
        # Set the size proportions (1:2:1)
        top_splitter.setStretchFactor(0, 1)  # Active calls
        top_splitter.setStretchFactor(1, 2)  # Map
        top_splitter.setStretchFactor(2, 1)  # Transcript
        
        layout.addWidget(top_splitter)
        
        # Bottom section - Conversation History
        history_widget = QWidget()
        history_layout = QVBoxLayout(history_widget)
        
        history_label = QLabel("Conversation History")
        history_label.setFont(QFont("Arial", 12, QFont.Bold))
        history_label.setStyleSheet("color: #2196F3; margin: 10px 0px 5px 0px;")
        history_layout.addWidget(history_label)
        
        self.active_conversation_tree = QTreeWidget()
        self.active_conversation_tree.setHeaderLabels([
            "UID", "Conversation", "Timestamp", "Summary",
            "Criticality", "isSpam", "User", "Location"
        ])
        self.active_conversation_tree.setColumnCount(8)
        self.active_conversation_tree.setAlternatingRowColors(True)
        self.active_conversation_tree.setStyleSheet("""
            QTreeWidget {
                background-color: #f5f5f5;
                border: 1px solid #ddd;
                border-radius: 4px;
            }
            QTreeWidget::item:alternate {
                background-color: #e0e0e0;
            }
            QHeaderView::section {
                background-color: #2196F3;
                color: white;
                padding: 5px;
                border: 1px solid #1976D2;
            }
        """)
        
        # Set column widths
        self.active_conversation_tree.setColumnWidth(0, 100)  # uid
        self.active_conversation_tree.setColumnWidth(1, 300)  # conversation
        self.active_conversation_tree.setColumnWidth(2, 150)  # timestamp
        self.active_conversation_tree.setColumnWidth(3, 300)  # summary
        self.active_conversation_tree.setColumnWidth(4, 100)  # criticality
        self.active_conversation_tree.setColumnWidth(5, 80)   # isSpam
        self.active_conversation_tree.setColumnWidth(6, 150)  # user
        self.active_conversation_tree.setColumnWidth(7, 150)  # location
        
        history_layout.addWidget(self.active_conversation_tree)
        layout.addWidget(history_widget)
        
        # Set layout proportions
        layout.setStretchFactor(top_splitter, 2)
        layout.setStretchFactor(history_widget, 1)
        
        return page
        
    def create_call_history_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Title
        title = QLabel("Call History")
        title.setFont(QFont("Arial", 16, QFont.Bold))
        layout.addWidget(title)
        
        # Filters section
        filters_layout = QHBoxLayout()
        
        # Date filter
        date_filter = QLineEdit()
        date_filter.setPlaceholderText("Filter by date (YYYY-MM-DD)")
        date_filter.setStyleSheet("""
            QLineEdit {
                padding: 8px;
                border: 1px solid #ddd;
                border-radius: 4px;
                background: white;
            }
        """)
        filters_layout.addWidget(date_filter)
        
        # Emergency type filter
        type_filter = QLineEdit()
        type_filter.setPlaceholderText("Filter by emergency type")
        type_filter.setStyleSheet("""
            QLineEdit {
                padding: 8px;
                border: 1px solid #ddd;
                border-radius: 4px;
                background: white;
            }
        """)
        filters_layout.addWidget(type_filter)
        
        # Apply filters button
        apply_filters_btn = QPushButton("Apply Filters")
        apply_filters_btn.setStyleSheet("""
            QPushButton {
                background-color: #007bff;
                color: white;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #0056b3;
            }
        """)
        filters_layout.addWidget(apply_filters_btn)
        
        layout.addLayout(filters_layout)
        
        # History table
        self.conversation_tree = QTreeWidget()
        self.conversation_tree.setHeaderLabels([
            "UID", "Conversation", "Timestamp", "Summary",
            "Criticality", "isSpam", "User", "Location"
        ])
        self.conversation_tree.setColumnCount(8)
        self.conversation_tree.setAlternatingRowColors(True)
        self.conversation_tree.setStyleSheet("""
            QTreeWidget {
                background-color: #f5f5f5;
                border: 1px solid #ddd;
                border-radius: 4px;
            }
            QTreeWidget::item:alternate {
                background-color: #e0e0e0;
            }
            QHeaderView::section {
                background-color: #2196F3;
                color: white;
                padding: 5px;
                border: 1px solid #1976D2;
            }
        """)
        
        # Set column widths
        self.conversation_tree.setColumnWidth(0, 100)  # uid
        self.conversation_tree.setColumnWidth(1, 300)  # conversation
        self.conversation_tree.setColumnWidth(2, 150)  # timestamp
        self.conversation_tree.setColumnWidth(3, 300)  # summary
        self.conversation_tree.setColumnWidth(4, 100)  # criticality
        self.conversation_tree.setColumnWidth(5, 80)   # isSpam
        self.conversation_tree.setColumnWidth(6, 150)  # user
        self.conversation_tree.setColumnWidth(7, 150)  # location
        
        layout.addWidget(self.conversation_tree)
        
        return page
        
    def create_analytics_page(self):
        page = QWidget()
        layout = QGridLayout(page)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(20)

        # Title
        title = QLabel("Call Analytics Dashboard")
        title.setFont(QFont("Arial", 18, QFont.Bold))
        title.setStyleSheet("color: #2196F3; margin-bottom: 10px;")
        layout.addWidget(title, 0, 0, 1, 2)

        # Time period filter
        filter_widget = QWidget()
        filter_layout = QHBoxLayout(filter_widget)
        filter_layout.setContentsMargins(0, 0, 0, 0)

        period_label = QLabel("Time Period:")
        period_label.setFont(QFont("Arial", 10))
        self.period_combo = QComboBox()
        self.period_combo.addItems(["Last 24 Hours", "Last Week", "Last Month", "All Time"])
        self.period_combo.setStyleSheet("""
            QComboBox {
                padding: 5px;
                border: 1px solid #ddd;
                border-radius: 4px;
                background: white;
                min-width: 150px;
            }
        """)
        self.period_combo.currentIndexChanged.connect(self.update_analytics)

        filter_layout.addWidget(period_label)
        filter_layout.addWidget(self.period_combo)
        filter_layout.addStretch()
        layout.addWidget(filter_widget, 1, 0, 1, 2)

        # Statistics cards
        stats_widget = QWidget()
        stats_layout = QHBoxLayout(stats_widget)
        stats_layout.setSpacing(20)

        # Total Calls Card
        self.total_calls_label = self.create_stat_card("Total Calls", "0")
        stats_layout.addWidget(self.total_calls_label)

        # Average Duration Card
        self.avg_duration_label = self.create_stat_card("Avg. Duration", "0 min")
        stats_layout.addWidget(self.avg_duration_label)

        # Emergency Rate Card
        self.emergency_rate_label = self.create_stat_card("Emergency Rate", "0%")
        stats_layout.addWidget(self.emergency_rate_label)

        # Spam Rate Card
        self.spam_rate_label = self.create_stat_card("Spam Rate", "0%")
        stats_layout.addWidget(self.spam_rate_label)

        layout.addWidget(stats_widget, 2, 0, 1, 2)

        # Charts
        # Location Distribution Chart
        self.location_chart = self.create_pie_chart("Call Distribution by Location")
        layout.addWidget(self.location_chart, 3, 0)

        # Emergency Type Distribution Chart
        self.type_chart = self.create_bar_chart("Emergency Type Distribution")
        layout.addWidget(self.type_chart, 3, 1)

        # Call Volume Timeline
        self.timeline_chart = self.create_line_chart("Call Volume Timeline")
        layout.addWidget(self.timeline_chart, 4, 0, 1, 2)

        return page

    def create_settings_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(20)

        # Title
        title = QLabel("Settings")
        title.setFont(QFont("Arial", 18, QFont.Bold))
        title.setStyleSheet("color: #2196F3; margin-bottom: 10px;")
        layout.addWidget(title)

        # Settings Container
        settings_container = QWidget()
        settings_container.setStyleSheet("""
            QWidget {
                background-color: white;
                border-radius: 8px;
                border: 1px solid #e0e0e0;
            }
        """)
        settings_layout = QVBoxLayout(settings_container)
        settings_layout.setContentsMargins(20, 20, 20, 20)
        settings_layout.setSpacing(15)

        # Dark Mode Section
        dark_mode_widget = QWidget()
        dark_mode_layout = QHBoxLayout(dark_mode_widget)
        dark_mode_layout.setContentsMargins(0, 0, 0, 0)

        dark_mode_label = QLabel("Dark Mode")
        dark_mode_label.setFont(QFont("Arial", 12))
        dark_mode_layout.addWidget(dark_mode_label)

        self.dark_mode_toggle = QPushButton()
        self.dark_mode_toggle.setCheckable(True)
        self.dark_mode_toggle.setChecked(self.dark_mode)
        self.dark_mode_toggle.setFixedSize(50, 25)
        self.dark_mode_toggle.setStyleSheet("""
            QPushButton {
                border: 2px solid #999;
                border-radius: 12px;
                background-color: #fff;
            }
            QPushButton:checked {
                background-color: #2196F3;
                border-color: #2196F3;
            }
            QPushButton::hover {
                border-color: #666;
            }
            QPushButton::checked:hover {
                border-color: #1976D2;
            }
        """)
        self.dark_mode_toggle.clicked.connect(self.toggle_dark_mode)
        dark_mode_layout.addWidget(self.dark_mode_toggle)
        dark_mode_layout.addStretch()

        settings_layout.addWidget(dark_mode_widget)
        settings_layout.addStretch()
        layout.addWidget(settings_container)
        layout.addStretch()

        return page

    def create_stat_card(self, title, value):
        card = QFrame()
        card.setStyleSheet("""
            QFrame {
                background-color: white;
                border-radius: 8px;
                padding: 15px;
                border: 1px solid #e0e0e0;
            }
        """)
        
        layout = QVBoxLayout(card)
        layout.setSpacing(5)
        
        title_label = QLabel(title)
        title_label.setObjectName("statCardTitle")
        title_label.setFont(QFont("Arial", 10))
        title_label.setStyleSheet("color: #666;")
        
        value_label = QLabel(value)
        value_label.setObjectName("statCardValue")
        value_label.setFont(QFont("Arial", 24, QFont.Bold))
        value_label.setStyleSheet("color: #2196F3;")
        
        layout.addWidget(title_label)
        layout.addWidget(value_label)
        
        return card

    def _update_stat_card(self, card, value):
        # Update the value label in the stat card
        value_label = card.findChild(QLabel, "statCardValue")
        if value_label:
            value_label.setText(value)
        else:
            print("Warning: Could not find value label in stat card")

    def create_pie_chart(self, title):
        series = QPieSeries()
        
        # Sample data - will be updated with real data
        series.append("Dubai", 30)
        series.append("Abu Dhabi", 20)
        series.append("Sharjah", 15)
        series.append("Other", 35)
        
        chart = QChart()
        chart.addSeries(series)
        chart.setTitle(title)
        chart.setAnimationOptions(QChart.SeriesAnimations)
        chart.legend().setVisible(True)
        chart.legend().setAlignment(Qt.AlignRight)
        
        # Style the title
        title_font = QFont()
        title_font.setBold(True)
        title_font.setPointSize(12)
        chart.setTitleFont(title_font)
        
        chartview = QChartView(chart)
        chartview.setRenderHint(QPainter.Antialiasing)
        
        return chartview

    def create_bar_chart(self, title):
        series = QBarSeries()
        
        # Empty bar set - data will be populated in update_analytics
        bar_set = QBarSet("Emergency Types")
        series.append(bar_set)
        
        chart = QChart()
        chart.addSeries(series)
        chart.setTitle(title)
        chart.setAnimationOptions(QChart.SeriesAnimations)
        
        categories = ["HIGH", "MEDIUM", "LOW", "SPAM"]
        axis_x = QBarCategoryAxis()
        axis_x.append(categories)
        axis_x.setTitleText("Emergency Criticality")  # Add x-axis title
        chart.addAxis(axis_x, Qt.AlignBottom)
        series.attachAxis(axis_x)
        
        axis_y = QValueAxis()
        axis_y.setRange(0, 10)  # Initial range, will be updated with real data
        axis_y.setTitleText("Number of Calls")  # Add y-axis title
        chart.addAxis(axis_y, Qt.AlignLeft)
        series.attachAxis(axis_y)
        
        # Make labels visible and styled
        axis_x.setLabelsFont(QFont("Arial", 9))
        axis_y.setLabelsFont(QFont("Arial", 9))
        
        # Style the title
        title_font = QFont()
        title_font.setBold(True)
        title_font.setPointSize(12)
        chart.setTitleFont(title_font)
        
        chart.legend().setVisible(False)
        
        chartview = QChartView(chart)
        chartview.setRenderHint(QPainter.Antialiasing)
        
        return chartview

    def create_line_chart(self, title):
        # Create an empty line series for call volume
        series = QLineSeries()
        series.setName("Call Volume")
        
        chart = QChart()
        chart.addSeries(series)
        chart.setTitle(title)
        chart.setAnimationOptions(QChart.SeriesAnimations)
        
        # Create axes
        axis_x = QDateTimeAxis()
        axis_x.setFormat("MMM dd")
        axis_x.setTitleText("Date")
        axis_x.setLabelsAngle(-45)  # Angle labels for better readability
        chart.addAxis(axis_x, Qt.AlignBottom)
        series.attachAxis(axis_x)
        
        axis_y = QValueAxis()
        axis_y.setLabelFormat("%d")
        axis_y.setTitleText("Number of Calls")
        chart.addAxis(axis_y, Qt.AlignLeft)
        series.attachAxis(axis_y)
        
        # Make labels visible and styled
        axis_x.setLabelsFont(QFont("Arial", 9))
        axis_y.setLabelsFont(QFont("Arial", 9))
        
        # Style the title
        title_font = QFont()
        title_font.setBold(True)
        title_font.setPointSize(12)
        chart.setTitleFont(title_font)
        
        chart.legend().setVisible(True)
        chart.legend().setAlignment(Qt.AlignBottom)
        
        chartview = QChartView(chart)
        chartview.setRenderHint(QPainter.Antialiasing)
        
        return chartview

    def update_analytics(self):
        try:
            period = self.period_combo.currentText()
            
            # Fetch data based on selected time period
            conn = sqlite3.connect("conversation.db")
            c = conn.cursor()
            
            # Query based on time period
            if period == "Last 24 Hours":
                time_filter = "datetime(timestamp) >= datetime('now', '-1 day')"
                days_to_look_back = 1
            elif period == "Last Week":
                time_filter = "datetime(timestamp) >= datetime('now', '-7 days')"
                days_to_look_back = 7
            elif period == "Last Month":
                time_filter = "datetime(timestamp) >= datetime('now', '-30 days')"
                days_to_look_back = 30
            else:  # All Time
                time_filter = "1=1"
                # Get the oldest record to determine range
                c.execute("SELECT julianday('now') - julianday(MIN(timestamp)) FROM conversations")
                result = c.fetchone()
                days_to_look_back = int(result[0]) if result and result[0] else 30  # Default to 30 if no data
            
            # Get total calls
            c.execute(f"SELECT COUNT(*) FROM conversations WHERE {time_filter}")
            total_calls = c.fetchone()[0]
            
            # Get spam rate
            c.execute(f"SELECT COUNT(*) FROM conversations WHERE isSpam = 1 AND {time_filter}")
            spam_calls = c.fetchone()[0]
            spam_rate = (spam_calls / total_calls * 100) if total_calls > 0 else 0
            
            # Get emergency distribution
            c.execute(f"SELECT criticality FROM conversations WHERE {time_filter}")
            criticalities = [row[0].upper() if row[0] else "UNKNOWN" for row in c.fetchall()]
            
            # Count different criticality levels
            high_priority = sum(1 for c in criticalities if c == 'HIGH')
            medium_priority = sum(1 for c in criticalities if c == 'MEDIUM')
            low_priority = sum(1 for c in criticalities if c == 'LOW')
            
            # Emergency rate is percentage of high criticality calls
            emergency_rate = (high_priority / total_calls * 100) if total_calls > 0 else 0
            
            # Get average call duration (simulated since we don't track actual duration)
            # Instead, let's use word count as a proxy for call duration
            c.execute(f"SELECT conversation FROM conversations WHERE {time_filter}")
            conversations = c.fetchall()
            total_words = sum(len(str(convo[0]).split()) for convo in conversations if convo[0])
            avg_words = total_words / total_calls if total_calls > 0 else 0
            # Assume average speaking rate of 150 words per minute
            avg_duration = avg_words / 150 if avg_words > 0 else 0
            
            # Get location distribution
            c.execute(f"SELECT location FROM conversations WHERE {time_filter}")
            locations = [row[0] if row[0] and row[0].lower() != "unknown" else "Other" for row in c.fetchall()]
            location_counts = Counter(locations)
            
            # Get data for call volume timeline
            c.execute(f"""
                SELECT 
                    date(timestamp) as call_date,
                    COUNT(*) as call_count
                FROM conversations
                WHERE {time_filter}
                GROUP BY date(timestamp)
                ORDER BY call_date
            """)
            date_counts = c.fetchall()
            
            # Update statistics cards
            self._update_stat_card(self.total_calls_label, str(total_calls))
            self._update_stat_card(self.avg_duration_label, f"{avg_duration:.1f} min")
            self._update_stat_card(self.emergency_rate_label, f"{emergency_rate:.1f}%")
            self._update_stat_card(self.spam_rate_label, f"{spam_rate:.1f}%")
            
            # Update location pie chart
            self._update_location_chart(location_counts)
            
            # Update criticality bar chart
            self._update_criticality_chart(high_priority, medium_priority, low_priority, spam_calls)
            
            # Update timeline chart
            self._update_timeline_chart(date_counts, days_to_look_back)
            
            conn.close()
            
        except Exception as e:
            print(f"Error updating analytics: {e}")
            import traceback
            traceback.print_exc()
            
    def _update_criticality_chart(self, high, medium, low, spam):
        # Update the emergency type bar chart with real data
        chart = self.type_chart.chart()
        
        # Remove existing series
        chart.removeAllSeries()
        
        # Create new series with actual data
        series = QBarSeries()
        bar_set = QBarSet("Emergency Types")
        bar_set.append([high, medium, low, spam])
        series.append(bar_set)
        
        # Add the series to the chart
        chart.addSeries(series)
        
        # Recreate axes
        categories = ["HIGH", "MEDIUM", "LOW", "SPAM"]
        axis_x = QBarCategoryAxis()
        axis_x.append(categories)
        axis_x.setTitleText("Emergency Criticality")  # Add x-axis title
        chart.addAxis(axis_x, Qt.AlignBottom)
        series.attachAxis(axis_x)
        
        # Update Y-axis range
        max_value = max(high, medium, low, spam)
        if max_value == 0:
            max_value = 10  # Default if no data
            
        axis_y = QValueAxis()
        axis_y.setRange(0, max_value * 1.1)  # Add 10% headroom
        axis_y.setLabelFormat("%d")
        axis_y.setTitleText("Number of Calls")  # Add y-axis title
        chart.addAxis(axis_y, Qt.AlignLeft)
        series.attachAxis(axis_y)
        
        # Make labels visible and styled
        axis_x.setLabelsFont(QFont("Arial", 9))
        axis_y.setLabelsFont(QFont("Arial", 9))
        
    def _update_timeline_chart(self, date_counts, days_to_look_back):
        from PyQt5.QtCore import QDateTime, Qt
        from PyQt5.QtChart import QLineSeries, QDateTimeAxis, QValueAxis
        
        # Get chart and clear existing series
        chart = self.timeline_chart.chart()
        chart.removeAllSeries()
        
        # Create a new series
        series = QLineSeries()
        series.setName("Call Volume")
        
        # If we have data points
        if date_counts:
            # Convert date strings to QDateTime and add to series
            max_count = 0
            for date_str, count in date_counts:
                try:
                    date = QDateTime.fromString(date_str, "yyyy-MM-dd")
                    series.append(date.toMSecsSinceEpoch(), count)
                    max_count = max(max_count, count)
                except Exception as e:
                    print(f"Error adding date point: {e} - {date_str}")
        else:
            # Add empty data point to avoid errors
            now = QDateTime.currentDateTime()
            series.append(now.toMSecsSinceEpoch(), 0)
            max_count = 10  # Default
            
        # Add series to chart
        chart.addSeries(series)
            
        # Create date axis
        axis_x = QDateTimeAxis()
        axis_x.setFormat("MMM dd")
        axis_x.setTitleText("Date")
        axis_x.setLabelsAngle(-45)  # Angle labels for better readability
        
        # Set range to cover the period
        now = QDateTime.currentDateTime()
        start_date = now.addDays(-days_to_look_back)
        axis_x.setRange(start_date, now)
        
        # Add axes
        chart.addAxis(axis_x, Qt.AlignBottom)
        series.attachAxis(axis_x)
        
        # Create value axis with appropriate range
        axis_y = QValueAxis()
        axis_y.setLabelFormat("%d")
        axis_y.setTitleText("Number of Calls")
        axis_y.setRange(0, max(max_count * 1.1, 5))  # Add 10% headroom, minimum of 5
        
        chart.addAxis(axis_y, Qt.AlignLeft)
        series.attachAxis(axis_y)
        
        # Make labels visible and styled
        axis_x.setLabelsFont(QFont("Arial", 9))
        axis_y.setLabelsFont(QFont("Arial", 9))

    def _update_location_chart(self, location_counts):
        # Update the location pie chart with new data
        series = QPieSeries()
        
        # Sort locations by count and take top 5
        top_locations = sorted(location_counts.items(), key=lambda x: x[1], reverse=True)[:5]
        other_count = sum(count for loc, count in location_counts.items() 
                         if (loc, count) not in top_locations)
        
        # Add top locations to pie chart
        for location, count in top_locations:
            series.append(location, count)
            # Set label visible for each slice
            last_slice = series.slices()[-1]
            last_slice.setLabelVisible(True)
        
        # Add "Other" if there are more locations
        if other_count > 0:
            series.append("Other", other_count)
            series.slices()[-1].setLabelVisible(True)
        
        # Update the chart
        chart = self.location_chart.chart()
        chart.removeAllSeries()
        chart.addSeries(series)
        
        # Ensure legend is visible and properly positioned
        chart.legend().setVisible(True)
        chart.legend().setAlignment(Qt.AlignRight)
        chart.legend().setFont(QFont("Arial", 9))

    def switch_page(self, index):
        # Update button states
        buttons = [self.active_calls_btn, self.call_history_btn, 
                  self.analytics_btn, self.settings_btn]
        for i, btn in enumerate(buttons):
            btn.setChecked(i == index)
        
        # Switch to selected page
        self.stacked_widget.setCurrentIndex(index)
        
        # If switching to analytics page, update the data
        if index == 2:  # Analytics page is at index 2
            self.update_analytics()

    def fetch_conversations(self):
        try:
            print("\nAttempting to fetch conversations from database...")
            conn = sqlite3.connect("conversation.db")
            c = conn.cursor()
            
            # First check if table exists
            c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='conversations'")
            if not c.fetchone():
                print("Table 'conversations' does not exist!")
                return []
            
            # Check table structure
            c.execute("PRAGMA table_info(conversations)")
            columns = c.fetchall()
            print("Table structure:", columns)
            
            # Get the count of records before fetching
            c.execute("SELECT COUNT(*) FROM conversations")
            count = c.fetchone()[0]
            print(f"Total records in database: {count}")
            
            # Fetch all conversations ordered by timestamp
            c.execute("SELECT * FROM conversations ORDER BY timestamp DESC")
            rows = c.fetchall()
            
            # Print detailed debug information
            print(f"\nFetched {len(rows)} conversations from database")
            if len(rows) == 0:
                print("Warning: No conversations found in database")
            else:
                print("\nFirst conversation data:")
                for idx, value in enumerate(rows[0]):
                    print(f"Column {idx}: {value}")
                print(f"\nLatest conversation timestamp: {rows[0][2]}")
            
            conn.close()
            return rows
            
        except sqlite3.Error as e:
            print(f"SQLite error: {e}")
            return []
        except Exception as e:
            print(f"Error fetching conversations: {e}")
            return []

    def update_conversation_list(self):
        print("\nUpdating conversation list...")
        self.conversation_tree.clear()
        self.active_conversation_tree.clear()  # Clear both trees
        self.active_calls_list.clear()  # Clear active calls list
        conversations = self.fetch_conversations()
        print(f"Fetched {len(conversations)} conversations from database")
        
        # If no conversations found, add some sample data for testing
        if not conversations:
            print("No conversations found, adding sample data for testing")
            sample_conversations = [
                (1, "There's a fire at Golden Gate Bridge!", "2023-07-15 14:30:22", "Fire at Golden Gate Bridge", "HIGH", 0, "John Doe", "Golden Gate Bridge"),
                (2, "Car accident on Main Street", "2023-07-15 15:45:10", "Accident at Main Street", "MEDIUM", 0, "Jane Smith", "Main Street"),
                (3, "Medical emergency at Central Park", "2023-07-15 16:20:05", "Medical at Central Park", "HIGH", 0, "Robert Brown", "Central Park"),
                (4, "Flooding in Downtown area", "2023-07-15 17:10:30", "Flooding at Downtown", "MEDIUM", 0, "Sarah Johnson", "Downtown"),
                (5, "Gas leak reported near School", "2023-07-15 18:05:45", "Gas leak at School", "HIGH", 0, "Michael Wilson", "City School")
            ]
            conversations = sample_conversations
        
        # Store the current scroll positions
        current_scroll = self.conversation_tree.verticalScrollBar().value()
        active_scroll = self.active_conversation_tree.verticalScrollBar().value()
        
        # Initialize call status dictionary if not exists
        if not hasattr(self, 'call_status'):
            self.call_status = {}  # uid -> {'dispatched': bool, 'resolved': bool}
        
        # Track if this is the first call being added
        is_first_call = len(self.active_calls_list) == 0
        
        for idx, convo in enumerate(conversations):
            try:
                # Create items for both trees
                history_item = QTreeWidgetItem(self.conversation_tree)
                active_item = QTreeWidgetItem(self.active_conversation_tree)
                
                # Map database columns to tree columns
                tree_values = [
                    str(convo[0]),  # UID
                    str(convo[1])[:100] + "..." if len(str(convo[1])) > 100 else str(convo[1]),  # Truncate conversation
                    str(convo[2]),  # Timestamp
                    str(convo[3]),  # Summary
                    str(convo[4]),  # Criticality
                    "Yes" if convo[5] == 1 else "No",  # isSpam
                    str(convo[6]),  # User
                    str(convo[7])   # Location
                ]
                
                # Set values for both trees
                for col, value in enumerate(tree_values):
                    history_item.setText(col, value)
                    active_item.setText(col, value)
                
                # Add to active calls list
                if idx < 5:  # Show only the 5 most recent calls
                    call_item = QListWidgetItem()
                    
                    # Set background color based on status
                    call_uid = tree_values[0]
                    
                    # Initialize status for new calls
                    if call_uid not in self.call_status:
                        self.call_status[call_uid] = {'dispatched': False, 'resolved': False}
                    
                    status = self.call_status[call_uid]
                    
                    # Create main card widget
                    call_widget = QFrame()
                    call_widget.setObjectName("callCard")
                    call_widget.setMinimumHeight(50)  # Set minimum height
                    
                    # Determine border color based on status
                    border_color = "#F44336"  # Default red
                    if status['resolved']:
                        border_color = "#4CAF50"  # Green for resolved
                    elif status['dispatched']:
                        border_color = "#FFEB3B"  # Yellow for dispatched
                    
                    # Basic styling for all cards
                    call_widget.setStyleSheet(f"""
                        #callCard {{
                            background-color: white;
                            border: none;
                            border-left: 4px solid {border_color};
                            padding: 10px 15px;
                        }}
                    """)
                    
                    # Use a grid layout for more control
                    card_layout = QGridLayout(call_widget)
                    card_layout.setContentsMargins(5, 5, 5, 5)
                    card_layout.setSpacing(2)
                    
                    # Create a label for emergency type and location with better visibility
                    emergency_info = QLabel(f"{tree_values[3]} - {tree_values[7]}")
                    emergency_info.setFont(QFont("Arial", 11, QFont.Bold))
                    emergency_info.setStyleSheet("color: #212121; padding: 2px;")
                    emergency_info.setWordWrap(True)
                    
                    # Time label
                    time_label = QLabel(f"Time: {tree_values[2].split(' ')[1]}")  # Only show time portion
                    time_label.setFont(QFont("Arial", 10))
                    time_label.setStyleSheet("color: #666666; padding: 2px;")
                    
                    # Add widgets to layout
                    card_layout.addWidget(emergency_info, 0, 0)
                    card_layout.addWidget(time_label, 1, 0)
                    
                    # Apply final styling to item
                    call_item.setSizeHint(QSize(call_widget.sizeHint().width(), 70))  # Force height
                    
                    # Store the conversation data in the item
                    call_item.setData(Qt.UserRole, convo)
                    
                    # Add to list
                    self.active_calls_list.addItem(call_item)
                    self.active_calls_list.setItemWidget(call_item, call_widget)
                    
                    # If this is the first call being added, update the map
                    if is_first_call and idx == 0:
                        location = tree_values[7]  # Get location from the conversation
                        if location and location.lower() != "unknown":
                            self.update_map_location(location)
                            print(f"Updated map with first call location: {location}")
                
                print(f"Added conversation {idx + 1}: {tree_values[0]} - {tree_values[6]} - {tree_values[7]}")
            except Exception as e:
                print(f"Error adding conversation {idx}: {str(e)}")
        
        # Restore scroll positions
        self.conversation_tree.verticalScrollBar().setValue(current_scroll)
        self.active_conversation_tree.verticalScrollBar().setValue(active_scroll)
        
        # Ensure the latest conversation is visible
        if conversations:
            self.conversation_tree.scrollToTop()
            self.active_conversation_tree.scrollToTop()
            print(f"Successfully added {len(conversations)} conversations to both trees")
        else:
            print("No conversations found in database")
        
        # Force the trees to update their display
        self.conversation_tree.update()
        self.active_conversation_tree.update()
        print("Conversation list update complete")

    def update_transcript(self):
        try:
            with open("conversations.txt", "r") as f:
                transcript_text = f.read()
                
                # Parse the conversation into individual messages
                lines = transcript_text.split("\n")
                chat_html = "<div class=\"chat-container\">"
                chat_html += "<h3 style=\"color: #333; border-bottom: 1px solid #ddd; padding-bottom: 5px; margin-top: 0;\">CALL TRANSCRIPT</h3>"
                
                for line in lines:
                    if line.strip():
                        if line.startswith("EVI:"):
                            # Operator message
                            message = line[4:].strip()
                            chat_html += f"""
                                <div class="message-row operator-row">
                                    <div class="operator-icon">🤖</div>
                                    <div class="operator-message">{message}</div>
                                </div>
                            """
                        elif line.startswith("You:"):
                            # Caller message
                            message = line[4:].strip()
                            chat_html += f"""
                                <div class="message-row caller-row">
                                    <div class="caller-icon">👤</div>
                                    <div class="caller-message">{message}</div>
                                </div>
                            """
                        elif not line.startswith("<"):  # Skip tags like <USER_INTERRUPTION>
                            # System message or untagged line
                            if line.strip():
                                chat_html += f"""
                                    <div style="text-align: center; color: #666; font-style: italic; margin: 8px 0; font-size: 12px;">
                                        {line.strip()}
                                    </div>
                                """
                
                chat_html += "</div>"
                
                # Update the HTML content
                self.transcript_area.setHtml(f"""
                    <html>
                    <head>
                        <style>
                            body {{ 
                                background-color: #f5f5f5; 
                                font-family: Arial, sans-serif;
                                margin: 0;
                                padding: 5px;
                            }}
                            .chat-container {{
                                display: flex;
                                flex-direction: column;
                                gap: 10px;
                            }}
                            .operator-message, .caller-message {{
                                max-width: 80%;
                                padding: 10px 14px;
                                border-radius: 18px;
                                margin: 2px 0;
                                position: relative;
                                display: inline-block;
                            }}
                            .operator-message {{
                                background-color: #e9e9e9;
                                color: #333;
                                align-self: flex-start;
                                margin-right: auto;
                                border-bottom-left-radius: 5px;
                            }}
                            .caller-message {{
                                background-color: #2979FF;
                                color: white;
                                align-self: flex-end;
                                margin-left: auto;
                                border-bottom-right-radius: 5px;
                            }}
                            .operator-icon, .caller-icon {{
                                width: 28px;
                                height: 28px;
                                background-color: #ccc;
                                border-radius: 50%;
                                display: inline-flex;
                                align-items: center;
                                justify-content: center;
                                margin-right: 8px;
                                vertical-align: top;
                                text-align: center;
                                font-size: 14px;
                            }}
                            .operator-icon {{
                                background-color: #e0e0e0;
                            }}
                            .caller-icon {{
                                background-color: #e0e0e0;
                                margin-right: 0;
                                margin-left: 8px;
                            }}
                            .message-row {{
                                display: flex;
                                margin-bottom: 12px;
                                align-items: flex-start;
                            }}
                            .operator-row {{
                                justify-content: flex-start;
                            }}
                            .caller-row {{
                                justify-content: flex-end;
                                flex-direction: row-reverse;
                            }}
                        </style>
                    </head>
                    <body>
                        {chat_html}
                    </body>
                    </html>
                """)
                
                # Scroll to the top to show the beginning of the conversation
                self.transcript_area.verticalScrollBar().setValue(0)
        except FileNotFoundError:
            pass

    def start_conversation_thread(self):
        self.start_button.setEnabled(False)
        self.end_button.setEnabled(True)
        self.transcript_area.clear()
        self.conv_thread = ConversationThread()
        self.conv_thread.finished.connect(self.on_conversation_finished)
        self.conv_thread.error.connect(self.on_conversation_error)
        self.conv_thread.start()
        
        self.update_timer.start(1000)

    def update_map_location(self, location):
        if location and location.lower() != "unknown":
            formatted_location = location.replace(' ', '+')
            html_content = f"""
            <html>
            <head>
                <style>
                    body {{ margin: 0; padding: 0; }}
                    iframe {{ width: 100%; height: 100%; border: none; }}
                </style>
            </head>
            <body>
                <iframe
                    src="https://www.google.com/maps/embed/v1/place?key=AIzaSyCR0nJhZTRbPgKn_r1tUqoQEN1JHAMcx3Q&q={formatted_location}"
                    allowfullscreen>
                </iframe>
            </body>
            </html>
            """
            self.map_view.setHtml(html_content)
            print(f"Updated map to show location: {location}")
        else:
            html_content = """
            <html>
            <head>
                <style>
                    body {{ margin: 0; padding: 0; }}
                    iframe {{ width: 100%; height: 100%; border: none; }}
                </style>
            </head>
            <body>
                <iframe
                    src="https://www.google.com/maps/embed/v1/place?key=AIzaSyCR0nJhZTRbPgKn_r1tUqoQEN1JHAMcx3Q&q=United+States"
                    allowfullscreen>
                </iframe>
            </body>
            </html>
            """
            self.map_view.setHtml(html_content)
            print("Reset map to default view (location unknown)")

    def check_summary_completion(self):
        if os.path.exists("summary_complete.txt"):
            print("Summary completion detected, reading conversation ID...")
            try:
                with open("summary_complete.txt", "r") as f:
                    conversation_id = f.read().strip()
                print(f"Found conversation ID: {conversation_id}")
                
                # Verify the conversation exists in the database
                conn = sqlite3.connect("conversation.db")
                c = conn.cursor()
                c.execute("SELECT * FROM conversations WHERE uid = ?", (conversation_id,))
                result = c.fetchone()
                conn.close()
                
                if result:
                    print(f"Verified conversation {conversation_id} exists in database")
                    # Update map with location from the conversation
                    location = result[7]  # Location is the 8th column (index 7)
                    if location and location.lower() != "unknown":
                        self.update_map_location(location)
                        print(f"Updated map with location: {location}")
                    else:
                        print("Location is unknown or empty, not updating map")
                else:
                    print(f"Warning: Conversation {conversation_id} not found in database")
                
                os.remove("summary_complete.txt")
                print("Removed summary_complete.txt")
                
                # Update the conversation list immediately
                print("Updating conversation list...")
                self.update_conversation_list()
                
                # Scroll to the top to show the latest conversation
                self.conversation_tree.scrollToTop()
                print("Scrolled to top")
                
                # Stop the summary check timer
                self.summary_check_timer.stop()
                print("Stopped summary check timer")
                
                # Enable the start button and disable the end button
                self.start_button.setEnabled(True)
                self.end_button.setEnabled(False)
                print("Updated button states")
                
                # Stop the transcript update timer
                self.update_timer.stop()
                print("Stopped transcript update timer")
                
                print("Conversation processing complete")
                QMessageBox.information(self, "Success", "Conversation has been processed and added to history.")
                
            except Exception as e:
                print(f"Error checking summary completion: {e}")
                QMessageBox.warning(self, "Warning", f"Error updating conversation list: {str(e)}")

    def on_conversation_finished(self):
        self.start_button.setEnabled(True)
        self.end_button.setEnabled(False)
        self.update_timer.stop()
        self.summary_check_timer.stop()
        print("Conversation finished, performing final update...")
        # Update the conversation list one final time to ensure we have the latest data
        self.update_conversation_list()
        QMessageBox.information(self, "Info", "Conversation has ended and summary has been generated.")

    def on_conversation_error(self, error_msg):
        self.start_button.setEnabled(True)
        self.end_button.setEnabled(False)
        self.update_timer.stop()
        self.summary_check_timer.stop()
        QMessageBox.critical(self, "Error", error_msg)

    def end_conversation(self):
        if self.conv_thread and self.conv_thread.isRunning():
            print("Ending conversation...")
            # Stop the conversation thread
            self.conv_thread.stop_conversation()
            self.end_button.setEnabled(False)
            QMessageBox.information(self, "Info", "Ending conversation and generating summary...\nPlease wait while the conversation is processed.")
            
            # Start checking for summary completion with a shorter interval
            self.summary_check_timer.start(500)  # Check every 500ms instead of 1000ms

    def toggle_dark_mode(self):
        self.dark_mode = self.dark_mode_toggle.isChecked()
        self.apply_theme()

    def apply_theme(self):
        if self.dark_mode:
            # Dark theme styles
            app_style = """
                QMainWindow, QWidget {
                    background-color: #1e1e1e;
                    color: #ffffff;
                }
                QLabel {
                    color: #ffffff;
                }
                QPushButton {
                    background-color: #2d2d2d;
                    color: #ffffff;
                    border: 1px solid #3d3d3d;
                    border-radius: 4px;
                }
                QPushButton:hover {
                    background-color: #3d3d3d;
                }
                QTreeWidget {
                    background-color: #2d2d2d;
                    color: #ffffff;
                    border: 1px solid #3d3d3d;
                }
                QTreeWidget::item {
                    color: #ffffff;
                }
                QTreeWidget::item:selected {
                    background-color: #3d3d3d;
                }
                QTreeWidget::item:alternate {
                    background-color: #363636;
                    color: #ffffff;
                }
                QHeaderView::section {
                    background-color: #2196F3;
                    color: white;
                    border: 1px solid #1976D2;
                }
                QTextEdit {
                    background-color: #2d2d2d;
                    color: #ffffff;
                    border: 1px solid #3d3d3d;
                }
                QLineEdit {
                    background-color: #2d2d2d;
                    color: #ffffff;
                    border: 1px solid #3d3d3d;
                }
                QComboBox {
                    background-color: #2d2d2d;
                    color: #ffffff;
                    border: 1px solid #3d3d3d;
                }
                QComboBox QAbstractItemView {
                    background-color: #2d2d2d;
                    color: #ffffff;
                    selection-background-color: #3d3d3d;
                }
                QFrame {
                    background-color: #2d2d2d;
                    border: 1px solid #3d3d3d;
                }
            """
            self.setStyleSheet(app_style)
            
            # Apply dark theme to conversation trees
            tree_style = """
                QTreeWidget {
                    background-color: #2d2d2d;
                    color: #ffffff;
                    border: 1px solid #3d3d3d;
                }
                QTreeWidget::item {
                    color: #ffffff;
                }
                QTreeWidget::item:selected {
                    background-color: #3d3d3d;
                }
                QTreeWidget::item:alternate {
                    background-color: #363636;
                    color: #ffffff;
                }
                QHeaderView::section {
                    background-color: #2196F3;
                    color: white;
                    border: 1px solid #1976D2;
                }
            """
            self.conversation_tree.setStyleSheet(tree_style)
            self.active_conversation_tree.setStyleSheet(tree_style)
            
            # Update navigation bar style for dark mode
            nav_bar = self.findChild(QWidget, "", Qt.FindDirectChildrenOnly)
            nav_bar_style = """
                QWidget {
                    background-color: #2d2d2d;
                    border-bottom: 1px solid #3d3d3d;
                }
                QPushButton {
                    background-color: transparent;
                    border: none;
                    padding: 15px 25px;
                    font-size: 14px;
                    color: #999999;
                }
                QPushButton:hover {
                    color: #2196F3;
                }
                QPushButton:checked {
                    color: #2196F3;
                    border-bottom: 2px solid #2196F3;
                    font-weight: bold;
                }
            """
            nav_bar.setStyleSheet(nav_bar_style)
            
            # Update transcript area
            transcript_style = """
                QTextEdit {
                    background-color: #2d2d2d;
                    color: #ffffff;
                    border: 1px solid #3d3d3d;
                    padding: 10px;
                    font-family: Arial;
                    font-size: 12px;
                }
            """
            self.transcript_area.setStyleSheet(transcript_style)
            
            # Update chart colors for analytics
            if hasattr(self, 'location_chart'):
                self.location_chart.chart().setBackgroundBrush(Qt.darkGray)
                self.location_chart.chart().setTitleBrush(Qt.white)
                self.location_chart.setStyleSheet("background-color: #2d2d2d;")
                # Update slices to have visible labels
                for series in self.location_chart.chart().series():
                    for slice in series.slices():
                        slice.setLabelBrush(Qt.white)
            
            if hasattr(self, 'type_chart'):
                self.type_chart.chart().setBackgroundBrush(Qt.darkGray)
                self.type_chart.chart().setTitleBrush(Qt.white)
                self.type_chart.setStyleSheet("background-color: #2d2d2d;")
                # Update axis colors for dark mode
                for axis in self.type_chart.chart().axes():
                    axis.setLabelsColor(Qt.white)
                    axis.setTitleBrush(Qt.white)
            
            if hasattr(self, 'timeline_chart'):
                self.timeline_chart.chart().setBackgroundBrush(Qt.darkGray)
                self.timeline_chart.chart().setTitleBrush(Qt.white)
                self.timeline_chart.setStyleSheet("background-color: #2d2d2d;")
                # Update axis colors for dark mode
                for axis in self.timeline_chart.chart().axes():
                    axis.setLabelsColor(Qt.white)
                    axis.setTitleBrush(Qt.white)
            
            # Update stat cards for dark mode
            stat_card_style = """
                QFrame {
                    background-color: #2d2d2d;
                    border-radius: 8px;
                    padding: 15px;
                    border: 1px solid #3d3d3d;
                }
                QLabel#statCardTitle {
                    color: #999999;
                }
                QLabel#statCardValue {
                    color: #2196F3;
                }
            """
            for card in [self.total_calls_label, self.avg_duration_label, 
                        self.emergency_rate_label, self.spam_rate_label]:
                card.setStyleSheet(stat_card_style)
                # Update value label color
                value_label = card.findChild(QLabel, "", Qt.FindChildrenRecursively)
                if value_label:
                    value_label.setProperty("value", True)
                    value_label.setStyleSheet("color: #2196F3;")
                # Update title label color
                title_label = card.layout().itemAt(0).widget()
                if title_label:
                    title_label.setStyleSheet("color: #999999;")
            
            # Update dispatch options for dark mode
            service_buttons = [self.police_button, self.fire_button, self.medic_button]
            for button in service_buttons:
                button.setStyleSheet("""
                    QPushButton {
                        background-color: #3d3d3d;
                        color: #ffffff;
                        padding: 8px 12px;
                        border: 1px solid #555555;
                        border-radius: 4px;
                        font-weight: bold;
                        min-width: 120px;
                        text-align: left;
                    }
                    QPushButton:hover {
                        background-color: #2979ff;
                        border-color: #2979ff;
                    }
                    QPushButton:pressed {
                        background-color: #2962ff;
                    }
                """)
            
            # Update styles for active calls list and call cards
            self.active_calls_list.setStyleSheet("""
                QListWidget {
                    background-color: #2d2d2d;
                    border: 1px solid #3d3d3d;
                    border-radius: 8px;
                    padding: 10px;
                }
                QListWidget::item {
                    margin-bottom: 8px;
                }
                QListWidget::item:selected {
                    background-color: #3d3d3d;
                }
                QListWidget::item:hover {
                    background-color: #363636;
                }
            """)
            
            # Update label of each card to be visible in dark mode
            self.update_call_cards_for_dark_mode(True)
            
        else:
            # Light theme styles
            self.setStyleSheet("")  # Reset to default light theme
            
            # Reset conversation trees style
            tree_style = """
                QTreeWidget {
                    background-color: #f5f5f5;
                    border: 1px solid #ddd;
                    border-radius: 4px;
                }
                QTreeWidget::item:alternate {
                    background-color: #e0e0e0;
                }
                QHeaderView::section {
                    background-color: #2196F3;
                    color: white;
                    padding: 5px;
                    border: 1px solid #1976D2;
                }
            """
            self.conversation_tree.setStyleSheet(tree_style)
            self.active_conversation_tree.setStyleSheet(tree_style)
            
            # Reset navigation bar style
            nav_bar = self.findChild(QWidget, "", Qt.FindDirectChildrenOnly)
            nav_bar_style = """
                QWidget {
                    background-color: #f8f9fa;
                    border-bottom: 1px solid #dee2e6;
                }
                QPushButton {
                    background-color: transparent;
                    border: none;
                    padding: 15px 25px;
                    font-size: 14px;
                    color: #6c757d;
                }
                QPushButton:hover {
                    color: #007bff;
                }
                QPushButton:checked {
                    color: #007bff;
                    border-bottom: 2px solid #007bff;
                    font-weight: bold;
                }
            """
            nav_bar.setStyleSheet(nav_bar_style)
            
            # Reset transcript area style
            transcript_style = """
                QTextEdit {
                    background-color: #f5f5f5;
                    border: 1px solid #ddd;
                    border-radius: 4px;
                    padding: 10px;
                    font-family: Arial;
                    font-size: 12px;
                }
            """
            self.transcript_area.setStyleSheet(transcript_style)
            
            # Reset chart colors
            if hasattr(self, 'location_chart'):
                self.location_chart.chart().setBackgroundBrush(Qt.white)
                self.location_chart.chart().setTitleBrush(Qt.black)
                self.location_chart.setStyleSheet("")
            
            if hasattr(self, 'type_chart'):
                self.type_chart.chart().setBackgroundBrush(Qt.white)
                self.type_chart.chart().setTitleBrush(Qt.black)
                self.type_chart.setStyleSheet("")
            
            if hasattr(self, 'timeline_chart'):
                self.timeline_chart.chart().setBackgroundBrush(Qt.white)
                self.timeline_chart.chart().setTitleBrush(Qt.black)
                self.timeline_chart.setStyleSheet("")
            
            # Reset stat cards to light mode
            stat_card_style = """
                QFrame {
                    background-color: white;
                    border-radius: 8px;
                    padding: 15px;
                    border: 1px solid #e0e0e0;
                }
                QLabel#statCardTitle {
                    color: #666666;
                }
                QLabel#statCardValue {
                    color: #2196F3;
                }
            """
            for card in [self.total_calls_label, self.avg_duration_label, 
                        self.emergency_rate_label, self.spam_rate_label]:
                card.setStyleSheet(stat_card_style)
                # Update value label color
                value_label = card.findChild(QLabel, "", Qt.FindChildrenRecursively)
                if value_label:
                    value_label.setProperty("value", True)
                    value_label.setStyleSheet("color: #2196F3;")
                # Update title label color
                title_label = card.layout().itemAt(0).widget()
                if title_label:
                    title_label.setStyleSheet("color: #666666;")
            
            # Update dispatch options for light mode
            service_buttons = [self.police_button, self.fire_button, self.medic_button]
            for button in service_buttons:
                button.setStyleSheet("""
                    QPushButton {
                        background-color: #ffffff;
                        color: #333333;
                        padding: 8px 12px;
                        border: 1px solid #dddddd;
                        border-radius: 4px;
                        font-weight: bold;
                        min-width: 120px;
                        text-align: left;
                    }
                    QPushButton:hover {
                        background-color: #e3f2fd;
                        border-color: #2196F3;
                        color: #2196F3;
                    }
                    QPushButton:pressed {
                        background-color: #bbdefb;
                    }
                """)
            
            # Update styles for active calls list and call cards
            self.active_calls_list.setStyleSheet("""
                QListWidget {
                    background-color: #f5f5f5;
                    border: 1px solid #ddd;
                    border-radius: 8px;
                    padding: 10px;
                }
                QListWidget::item {
                    margin-bottom: 8px;
                }
                QListWidget::item:selected {
                    background-color: #e3f2fd;
                }
                QListWidget::item:hover {
                    background-color: #f8f9fa;
                }
            """)
            
            # Update label of each card to be visible in light mode
            self.update_call_cards_for_dark_mode(False)
        
        # Preserve specific button styles
        self.update_component_styles()

    def update_component_styles(self):
        # Update navigation bar style
        nav_bar_style = """
            QWidget {
                background-color: """ + ("#2d2d2d" if self.dark_mode else "#f8f9fa") + """;
                border-bottom: 1px solid """ + ("#3d3d3d" if self.dark_mode else "#dee2e6") + """;
            }
            QPushButton {
                background-color: transparent;
                border: none;
                padding: 15px 25px;
                font-size: 14px;
                color: """ + ("#999" if self.dark_mode else "#6c757d") + """;
            }
            QPushButton:hover {
                color: #007bff;
            }
            QPushButton:checked {
                color: #007bff;
                border-bottom: 2px solid #007bff;
                font-weight: bold;
            }
        """
        self.findChild(QWidget, "", Qt.FindDirectChildrenOnly).setStyleSheet(nav_bar_style)

        # Update start button style
        start_button_style = """
            QPushButton {
                background-color: #4CAF50;
                color: white;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:disabled {
                background-color: #cccccc;
            }
        """
        self.start_button.setStyleSheet(start_button_style)

        # Update end button style
        end_button_style = """
            QPushButton {
                background-color: #ff9800;
                color: white;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #f57c00;
            }
            QPushButton:disabled {
                background-color: #cccccc;
            }
        """
        self.end_button.setStyleSheet(end_button_style)

    def on_active_call_clicked(self, item):
        # Get the conversation data stored in the item
        convo = item.data(Qt.UserRole)
        if convo:
            # Show details dialog
            details_dialog = DetailsDialog(self, convo)
            
            # Get the position of the transcript area in global coordinates
            transcript_pos = self.transcript_area.mapToGlobal(self.transcript_area.rect().topLeft())
            
            # Calculate position - place dialog immediately to the left of transcript
            dialog_x = transcript_pos.x() - details_dialog.width()
            dialog_y = transcript_pos.y()  # Align with top of transcript
            
            # Ensure dialog stays within screen bounds
            screen = QApplication.primaryScreen().geometry()
            if dialog_x < screen.left():
                # If it would go off screen to the left, place it immediately to the right of transcript instead
                dialog_x = transcript_pos.x() + self.transcript_area.width()
            
            # Set position and show the dialog
            details_dialog.move(dialog_x, dialog_y)
            details_dialog.show()  # Use show() instead of exec_() for non-modal behavior
            
            # Update map with location
            self.update_map_location(str(convo[7]))  # location is at index 7
            
            # Update transcript area with the conversation
            conversation_text = str(convo[1])  # conversation text is at index 1
            
            # Parse the conversation into individual messages
            chat_html = "<div class=\"chat-container\">"
            chat_html += "<h3 style=\"color: #333; border-bottom: 1px solid #ddd; padding-bottom: 5px; margin-top: 0;\">CALL TRANSCRIPT</h3>"
            
            lines = conversation_text.split("\n")
            for line in lines:
                if line.strip():
                    if line.startswith("EVI:"):
                        # Operator message
                        message = line[4:].strip()
                        chat_html += f"""
                            <div class="message-row operator-row">
                                <div class="operator-icon">🤖</div>
                                <div class="operator-message">{message}</div>
                            </div>
                        """
                    elif line.startswith("You:"):
                        # Caller message
                        message = line[4:].strip()
                        chat_html += f"""
                            <div class="message-row caller-row">
                                <div class="caller-icon">👤</div>
                                <div class="caller-message">{message}</div>
                            </div>
                        """
                    elif not line.startswith("<"):  # Skip tags like <USER_INTERRUPTION>
                        # System message or untagged line
                        if line.strip():
                            chat_html += f"""
                                <div style="text-align: center; color: #666; font-style: italic; margin: 8px 0; font-size: 12px;">
                                    {line.strip()}
                                </div>
                            """
            
            chat_html += "</div>"
            
            # Update the HTML content
            self.transcript_area.setHtml(f"""
                <html>
                <head>
                    <style>
                        body {{ 
                            background-color: #f5f5f5; 
                            font-family: Arial, sans-serif;
                            margin: 0;
                            padding: 5px;
                        }}
                        .chat-container {{
                            display: flex;
                            flex-direction: column;
                            gap: 10px;
                        }}
                        .operator-message, .caller-message {{
                            max-width: 80%;
                            padding: 10px 14px;
                            border-radius: 18px;
                            margin: 2px 0;
                            position: relative;
                            display: inline-block;
                        }}
                        .operator-message {{
                            background-color: #e9e9e9;
                            color: #333;
                            align-self: flex-start;
                            margin-right: auto;
                            border-bottom-left-radius: 5px;
                        }}
                        .caller-message {{
                            background-color: #2979FF;
                            color: white;
                            align-self: flex-end;
                            margin-left: auto;
                            border-bottom-right-radius: 5px;
                        }}
                        .operator-icon, .caller-icon {{
                            width: 28px;
                            height: 28px;
                            background-color: #ccc;
                            border-radius: 50%;
                            display: inline-flex;
                            align-items: center;
                            justify-content: center;
                            margin-right: 8px;
                            vertical-align: top;
                            text-align: center;
                            font-size: 14px;
                        }}
                        .operator-icon {{
                            background-color: #e0e0e0;
                        }}
                        .caller-icon {{
                            background-color: #e0e0e0;
                            margin-right: 0;
                            margin-left: 8px;
                        }}
                        .message-row {{
                            display: flex;
                            margin-bottom: 12px;
                            align-items: flex-start;
                        }}
                        .operator-row {{
                            justify-content: flex-start;
                        }}
                        .caller-row {{
                            justify-content: flex-end;
                            flex-direction: row-reverse;
                        }}
                    </style>
                </head>
                <body>
                    {chat_html}
                </body>
                </html>
            """)
            
            # Scroll to the top to show the beginning of the conversation
            self.transcript_area.verticalScrollBar().setValue(0)

    def show_dispatch_options(self):
        """Show the dispatch options buttons."""
        if not self.active_calls_list.currentItem():
            QMessageBox.warning(self, "Warning", "Please select an active call first.")
            return
        
        if self.dispatch_options.isVisible():
            self.dispatch_options.hide()
        else:
            self.dispatch_options.show()

    def handle_dispatch_button(self, service):
        """Handle the dispatch button click with the specified service."""
        selected_item = self.active_calls_list.currentItem()
        if not selected_item:
            return
            
        location = "Unknown"
        
        # Get location from the selected call
        call_data = selected_item.data(Qt.UserRole)
        if call_data and len(call_data) > 7:
            location = str(call_data[7])
            call_uid = str(call_data[0])
            
            # Update status to dispatched
            if hasattr(self, 'call_status') and call_uid in self.call_status:
                self.call_status[call_uid]['dispatched'] = True
                # Update UI
                self.update_conversation_list()
        
        # Create a custom message box for dispatch confirmation
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("Dispatch Confirmation")
        
        # Set icon based on service type
        if service == "Police":
            msg_box.setIconPixmap(QLabel("🚓").grab())
        elif service == "Firefighters":
            msg_box.setIconPixmap(QLabel("🚒").grab())
        elif service == "Paramedics":
            msg_box.setIconPixmap(QLabel("🚑").grab())
        
        msg_box.setText(f"{service} have been dispatched to {location}.")
        msg_box.setStandardButtons(QMessageBox.Ok)
        msg_box.exec_()
        
        # Hide options after dispatching
        self.dispatch_options.hide()

    def mark_as_resolved(self):
        """Mark the selected call as resolved."""
        selected_item = self.active_calls_list.currentItem()
        if not selected_item:
            QMessageBox.warning(self, "Warning", "Please select an active call first.")
            return
        
        # Get call data
        call_data = selected_item.data(Qt.UserRole)
        if call_data:
            call_uid = str(call_data[0])
            location = str(call_data[7]) if len(call_data) > 7 else "Unknown"
            
            # Update status to resolved
            if hasattr(self, 'call_status') and call_uid in self.call_status:
                self.call_status[call_uid]['resolved'] = True
                # Update UI
                self.update_conversation_list()
            
            # Display confirmation
            QMessageBox.information(
                self,
                "Resolution Confirmation",
                f"The emergency call from {location} has been marked as resolved."
            )

    def update_call_cards_for_dark_mode(self, is_dark):
        """Update the call cards to maintain visibility in different themes"""
        for i in range(self.active_calls_list.count()):
            item = self.active_calls_list.item(i)
            card_widget = self.active_calls_list.itemWidget(item)
            
            if card_widget:
                # Get current border color based on status
                call_data = item.data(Qt.UserRole)
                call_uid = str(call_data[0]) if call_data else ""
                
                border_color = "#F44336"  # Default red
                if call_uid in self.call_status:
                    status = self.call_status[call_uid]
                    if status['resolved']:
                        border_color = "#4CAF50"  # Green for resolved
                    elif status['dispatched']:
                        border_color = "#FFEB3B"  # Yellow for dispatched
                
                # Update card background and text colors
                if is_dark:
                    # Dark mode card
                    bg_color = "#2d2d2d"
                    text_color = "#ffffff"
                    secondary_color = "#bbbbbb"
                    
                    card_widget.setStyleSheet(f"""
                        #callCard {{
                            background-color: {bg_color};
                            border: none;
                            border-left: 4px solid {border_color};
                            padding: 10px 15px;
                        }}
                    """)
                else:
                    # Light mode card
                    bg_color = "white"
                    text_color = "#212121"
                    secondary_color = "#666666"
                    
                    card_widget.setStyleSheet(f"""
                        #callCard {{
                            background-color: {bg_color};
                            border: none;
                            border-left: 4px solid {border_color};
                            padding: 10px 15px;
                        }}
                    """)
                
                # Update all labels in the card
                labels = card_widget.findChildren(QLabel)
                for label in labels:
                    if "Time:" in label.text():
                        label.setStyleSheet(f"color: {secondary_color}; padding: 2px;")
                    else:
                        label.setStyleSheet(f"color: {text_color}; padding: 2px;")

class LoginWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Emergency Response System - Login")
        self.setGeometry(100, 100, 400, 500)
        self.setStyleSheet("""
            QMainWindow {
                background-color: white;
            }
            QLabel {
                color: #333;
            }
            QLineEdit {
                padding: 10px;
                border: 1px solid #ddd;
                border-radius: 4px;
                font-size: 14px;
            }
            QPushButton {
                padding: 12px;
                border: none;
                border-radius: 4px;
                font-size: 14px;
                font-weight: bold;
                color: white;
            }
            QPushButton#loginButton {
                background-color: #007BFF;
            }
            QPushButton#loginButton:hover {
                background-color: #0069D9;
            }
            QPushButton#createAccountButton {
                background-color: #28A745;
            }
            QPushButton#createAccountButton:hover {
                background-color: #218838;
            }
        """)
        
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        
        # Main layout
        main_layout = QVBoxLayout(self.central_widget)
        main_layout.setContentsMargins(40, 40, 40, 40)
        
        # Title
        title = QLabel("Emergency Response System")
        title.setFont(QFont("Arial", 18, QFont.Bold))
        title.setStyleSheet("color: #333; margin-bottom: 30px;")
        title.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(title)
        
        # Login container
        login_container = QFrame()
        login_container.setFrameShape(QFrame.StyledPanel)
        login_container.setStyleSheet("""
            QFrame {
                background-color: white;
                border: 1px solid #ddd;
                border-radius: 8px;
                padding: 20px;
            }
        """)
        login_layout = QVBoxLayout(login_container)
        login_layout.setSpacing(15)
        
        # Username input
        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("Username")
        login_layout.addWidget(self.username_input)
        
        # Password input
        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("Password")
        self.password_input.setEchoMode(QLineEdit.Password)
        login_layout.addWidget(self.password_input)
        
        # Login button
        self.login_button = QPushButton("Login")
        self.login_button.setObjectName("loginButton")
        self.login_button.clicked.connect(self.login)
        login_layout.addWidget(self.login_button)
        
        # Create account button
        self.create_account_button = QPushButton("Create Account")
        self.create_account_button.setObjectName("createAccountButton")
        self.create_account_button.clicked.connect(self.show_create_account)
        login_layout.addWidget(self.create_account_button)
        
        main_layout.addWidget(login_container)
        
        # Version info
        version_label = QLabel("Version 1.0.0")
        version_label.setAlignment(Qt.AlignCenter)
        version_label.setStyleSheet("color: #999; margin-top: 15px;")
        main_layout.addWidget(version_label)
        
        # Set up database for user accounts
        self.setup_database()
        
        # Initialize status message label
        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: red; margin-top: 10px;")
        self.status_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(self.status_label)
        
        # Create account form (initially hidden)
        self.create_account_widget = QWidget()
        create_account_layout = QVBoxLayout(self.create_account_widget)
        
        create_account_title = QLabel("Create Account")
        create_account_title.setFont(QFont("Arial", 16, QFont.Bold))
        create_account_title.setAlignment(Qt.AlignCenter)
        create_account_layout.addWidget(create_account_title)
        
        self.new_username_input = QLineEdit()
        self.new_username_input.setPlaceholderText("New Username")
        create_account_layout.addWidget(self.new_username_input)
        
        self.new_password_input = QLineEdit()
        self.new_password_input.setPlaceholderText("New Password")
        self.new_password_input.setEchoMode(QLineEdit.Password)
        create_account_layout.addWidget(self.new_password_input)
        
        self.confirm_password_input = QLineEdit()
        self.confirm_password_input.setPlaceholderText("Confirm Password")
        self.confirm_password_input.setEchoMode(QLineEdit.Password)
        create_account_layout.addWidget(self.confirm_password_input)
        
        create_button = QPushButton("Create Account")
        create_button.setObjectName("loginButton")  # Reuse same styling
        create_button.clicked.connect(self.create_account)
        create_account_layout.addWidget(create_button)
        
        back_button = QPushButton("Back to Login")
        back_button.clicked.connect(self.show_login)
        create_account_layout.addWidget(back_button)
        
        self.create_account_widget.hide()
        main_layout.addWidget(self.create_account_widget)
        
    def setup_database(self):
        # Set up database for user accounts
        conn = sqlite3.connect('users.db')
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS users
                    (username TEXT PRIMARY KEY, password TEXT)''')
        conn.commit()
        conn.close()
        
        # Create a default admin user if it doesn't exist
        self.create_default_user()
    
    def create_default_user(self):
        conn = sqlite3.connect('users.db')
        c = conn.cursor()
        
        # Check if admin user exists
        c.execute("SELECT * FROM users WHERE username=?", ("admin",))
        if not c.fetchone():
            # Create default admin user with password 'admin'
            hashed_password = hashlib.sha256("admin".encode()).hexdigest()
            c.execute("INSERT INTO users VALUES (?, ?)", ("admin", hashed_password))
            conn.commit()
            print("Created default admin user")
        
        conn.close()
    
    def show_create_account(self):
        self.create_account_widget.show()
        self.login_button.setEnabled(False)
        self.create_account_button.setEnabled(False)
        self.username_input.setEnabled(False)
        self.password_input.setEnabled(False)
    
    def show_login(self):
        self.create_account_widget.hide()
        self.login_button.setEnabled(True)
        self.create_account_button.setEnabled(True)
        self.username_input.setEnabled(True)
        self.password_input.setEnabled(True)
        self.status_label.setText("")
    
    def create_account(self):
        username = self.new_username_input.text()
        password = self.new_password_input.text()
        confirm_password = self.confirm_password_input.text()
        
        if not username or not password:
            self.status_label.setText("Username and password are required")
            return
        
        if password != confirm_password:
            self.status_label.setText("Passwords do not match")
            return
        
        # Check if username already exists
        conn = sqlite3.connect('users.db')
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE username=?", (username,))
        if c.fetchone():
            self.status_label.setText("Username already exists")
            conn.close()
            return
        
        # Create new user
        hashed_password = hashlib.sha256(password.encode()).hexdigest()
        c.execute("INSERT INTO users VALUES (?, ?)", (username, hashed_password))
        conn.commit()
        conn.close()
        
        self.status_label.setText("Account created successfully")
        
        # Clear inputs and go back to login
        self.new_username_input.clear()
        self.new_password_input.clear()
        self.confirm_password_input.clear()
        self.show_login()
    
    def login(self):
        username = self.username_input.text()
        password = self.password_input.text()
        
        if not username or not password:
            self.status_label.setText("Username and password are required")
            return
        
        # Check credentials
        conn = sqlite3.connect('users.db')
        c = conn.cursor()
        c.execute("SELECT password FROM users WHERE username=?", (username,))
        user = c.fetchone()
        conn.close()
        
        if not user:
            self.status_label.setText("Invalid username or password")
            return
        
        hashed_password = hashlib.sha256(password.encode()).hexdigest()
        if hashed_password != user[0]:
            self.status_label.setText("Invalid username or password")
            return
        
        # Login successful, launch main application
        self.main_app = VoiceAnalysisUI()
        self.main_app.show()
        self.close()

class DetailsDialog(QDialog):
    def __init__(self, parent=None, call_data=None):
        super().__init__(parent)
        self.setWindowTitle("Details")
        self.setFixedSize(350, 500)
        # Set proper window flags to make it behave like a popup
        self.setWindowFlags(Qt.Popup | Qt.FramelessWindowHint)
        self.setStyleSheet("""
            QDialog {
                background-color: white;
                border-radius: 12px;
                border: 1px solid #e0e0e0;
            }
            QDialog {
                background: white;
            }
            QLabel {
                color: #333;
            }
            QLabel#title {
                font-size: 20px;
                font-weight: bold;
                color: #1a1a1a;
            }
            QLabel#critical {
                background-color: #ff4444;
                color: white;
                padding: 4px 8px;
                border-radius: 4px;
                font-size: 12px;
            }
            QLabel#infoLabel {
                color: #666;
                font-size: 13px;
                font-weight: bold;
            }
            QLabel#infoValue {
                color: #333;
                font-size: 13px;
            }
        """)

        # Create and set up the shadow effect
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(15)
        shadow.setXOffset(0)
        shadow.setYOffset(2)
        shadow.setColor(QColor(0, 0, 0, 50))  # Semi-transparent black
        self.setGraphicsEffect(shadow)

        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)

        if call_data:
            # Header section with close button
            header_layout = QHBoxLayout()
            
            # Title
            title = QLabel(str(call_data[3]))  # Summary as title
            title.setObjectName("title")
            title.setWordWrap(True)
            header_layout.addWidget(title)
            
            # Close button
            close_button = QPushButton("✕")
            close_button.setFixedSize(24, 24)
            close_button.setStyleSheet("""
                QPushButton {
                    background-color: transparent;
                    border: none;
                    color: #999;
                    font-size: 16px;
                }
                QPushButton:hover {
                    color: #333;
                }
            """)
            close_button.clicked.connect(self.close)
            header_layout.addWidget(close_button)
            
            layout.addLayout(header_layout)
            
            # Criticality badge
            critical_label = QLabel("CRITICAL" if str(call_data[4]).upper() == "HIGH" else str(call_data[4]).upper())
            critical_label.setObjectName("critical")
            critical_label.setStyleSheet(f"""
                QLabel {{
                    background-color: {
                        '#ff4444' if str(call_data[4]).upper() == 'HIGH'
                        else '#ffbb33' if str(call_data[4]).upper() == 'MEDIUM'
                        else '#00C851'
                    };
                    color: white;
                    padding: 4px 8px;
                    border-radius: 4px;
                    font-size: 12px;
                }}
            """)
            critical_layout = QHBoxLayout()
            critical_layout.addWidget(critical_label)
            critical_layout.addStretch()
            layout.addLayout(critical_layout)
            
            # Info grid (Time and Location)
            info_grid = QGridLayout()
            info_grid.setSpacing(10)
            
            # Time of Call
            time_label = QLabel("Time of Call")
            time_label.setObjectName("infoLabel")
            info_grid.addWidget(time_label, 0, 0)
            
            time_value = QLabel(str(call_data[2]).split()[1])  # Extract time from timestamp
            time_value.setObjectName("infoValue")
            info_grid.addWidget(time_value, 0, 1)
            
            # Location
            location_label = QLabel("Location")
            location_label.setObjectName("infoLabel")
            info_grid.addWidget(location_label, 1, 0)
            
            location_value = QLabel(str(call_data[7]))
            location_value.setObjectName("infoValue")
            info_grid.addWidget(location_value, 1, 1)
            
            layout.addLayout(info_grid)
            
            # Street View Image
            try:
                api_key = os.getenv("GMAP_API_KEY")
                location = str(call_data[7])
                street_view_url = f"https://maps.googleapis.com/maps/api/streetview?size=400x200&location={location}&key={api_key}"  # Reduced image size
                
                response = requests.get(street_view_url)
                image = QPixmap()
                image.loadFromData(response.content)
                
                # Scale the image to fit the dialog width while maintaining aspect ratio
                image = image.scaledToWidth(310, Qt.SmoothTransformation)  # Adjusted to fit smaller dialog
                
                image_label = QLabel()
                image_label.setPixmap(image)
                image_label.setStyleSheet("""
                    QLabel {
                        border-radius: 8px;
                        margin: 10px 0;
                    }
                """)
                layout.addWidget(image_label)
            except Exception as e:
                print(f"Error loading street view image: {e}")
            
            # Summary section
            summary_label = QLabel("Summary")
            summary_label.setObjectName("infoLabel")
            layout.addWidget(summary_label)
            
            summary_text = QLabel(str(call_data[3]))
            summary_text.setWordWrap(True)
            summary_text.setStyleSheet("""
                QLabel {
                    font-size: 13px;
                    line-height: 1.4;
                    color: #333;
                    background-color: #f8f9fa;
                    padding: 12px;
                    border-radius: 4px;
                }
            """)
            layout.addWidget(summary_text)
            
            layout.addStretch()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    login_window = LoginWindow()
    login_window.show()
    sys.exit(app.exec_())
