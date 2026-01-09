"""
File Upload Component for DynoAI PyQt6 GUI
Drag-and-drop file selection widget matching the React FileUpload component
"""

import os
from typing import Optional

from PyQt6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QWidget, QFileDialog, QSizePolicy
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QDragEnterEvent, QDropEvent, QCursor


class FileUploadWidget(QFrame):
    """
    Drag-and-drop file upload widget.
    Supports file selection via drag-drop or file dialog.
    """
    
    # Signals
    file_selected = pyqtSignal(str)  # Emits file path
    file_cleared = pyqtSignal()
    
    def __init__(
        self,
        accept: str = ".csv,.txt",
        max_size_mb: int = 50,
        parent: Optional[QWidget] = None
    ):
        super().__init__(parent)
        
        self.accept = accept
        self.max_size_mb = max_size_mb
        self._selected_file: Optional[str] = None
        self._is_dragging = False
        
        # Enable drag and drop
        self.setAcceptDrops(True)
        
        # Initial style
        self.setProperty("class", "drop-zone")
        
        # Layout
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(32, 32, 32, 32)
        self._layout.setSpacing(16)
        self._layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Build UI
        self._build_empty_state()
        
        # Size policy
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        self.setMinimumHeight(200)
        
    def _build_empty_state(self) -> None:
        """Build the empty state UI (no file selected)."""
        self._clear_layout()
        
        # Upload icon
        self.icon_label = QLabel("📤")
        self.icon_label.setStyleSheet("font-size: 32pt; background: transparent;")
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._layout.addWidget(self.icon_label)
        
        # Main text
        self.main_text = QLabel("Drop your CSV file here")
        self.main_text.setStyleSheet("""
            font-size: 14pt;
            font-weight: 600;
            background: transparent;
        """)
        self.main_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._layout.addWidget(self.main_text)
        
        # Secondary text
        self.secondary_text = QLabel("or click to browse")
        self.secondary_text.setProperty("class", "muted")
        self.secondary_text.setStyleSheet("background: transparent;")
        self.secondary_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._layout.addWidget(self.secondary_text)
        
        # Hint text
        self.hint_text = QLabel(
            f"Supports WinPEP, PowerVision, and generic CSV formats (Max {self.max_size_mb}MB)"
        )
        self.hint_text.setProperty("class", "muted")
        self.hint_text.setStyleSheet("""
            font-size: 8pt;
            background: transparent;
        """)
        self.hint_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._layout.addWidget(self.hint_text)
        
        # Make the whole widget clickable
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        
    def _build_selected_state(self, file_path: str) -> None:
        """Build the selected state UI (file is selected)."""
        self._clear_layout()
        
        # File info container
        file_container = QHBoxLayout()
        file_container.setSpacing(16)
        
        # File icon
        file_icon = QLabel("📄")
        file_icon.setStyleSheet("font-size: 24pt; background: transparent;")
        file_container.addWidget(file_icon)
        
        # File info
        info_layout = QVBoxLayout()
        info_layout.setSpacing(4)
        
        filename = os.path.basename(file_path)
        self.filename_label = QLabel(filename)
        self.filename_label.setStyleSheet("""
            font-weight: 600;
            background: transparent;
        """)
        info_layout.addWidget(self.filename_label)
        
        # File size
        try:
            size_bytes = os.path.getsize(file_path)
            size_mb = size_bytes / (1024 * 1024)
            size_text = f"{size_mb:.2f} MB"
        except Exception:
            size_text = "Unknown size"
            
        self.size_label = QLabel(size_text)
        self.size_label.setProperty("class", "value")
        self.size_label.setStyleSheet("""
            font-size: 9pt;
            background: transparent;
        """)
        info_layout.addWidget(self.size_label)
        
        file_container.addLayout(info_layout)
        file_container.addStretch()
        
        # Clear button
        self.clear_btn = QPushButton("✕")
        self.clear_btn.setProperty("variant", "ghost")
        self.clear_btn.setFixedSize(32, 32)
        self.clear_btn.setToolTip("Remove file")
        self.clear_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.clear_btn.clicked.connect(self.clear_file)
        file_container.addWidget(self.clear_btn)
        
        # Add to main layout
        container_widget = QWidget()
        container_widget.setLayout(file_container)
        self._layout.addWidget(container_widget)
        
        # Remove click cursor since file is selected
        self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))
        
    def _clear_layout(self) -> None:
        """Remove all widgets from layout."""
        while self._layout.count():
            item = self._layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                # Clear nested layout
                while item.layout().count():
                    sub_item = item.layout().takeAt(0)
                    if sub_item.widget():
                        sub_item.widget().deleteLater()
                        
    def _validate_file(self, file_path: str) -> tuple[bool, str]:
        """
        Validate the selected file.
        Returns (is_valid, error_message).
        """
        # Check if file exists
        if not os.path.exists(file_path):
            return False, "File not found"
            
        # Check extension
        _, ext = os.path.splitext(file_path)
        allowed_extensions = [e.strip().lower() for e in self.accept.split(',')]
        if ext.lower() not in allowed_extensions:
            return False, f"Invalid file type. Allowed: {self.accept}"
            
        # Check file size
        size_bytes = os.path.getsize(file_path)
        size_mb = size_bytes / (1024 * 1024)
        if size_mb > self.max_size_mb:
            return False, f"File too large. Maximum size: {self.max_size_mb}MB"
            
        return True, ""
        
    def _handle_file(self, file_path: str) -> None:
        """Handle a selected file."""
        is_valid, error = self._validate_file(file_path)
        
        if is_valid:
            self._selected_file = file_path
            self._build_selected_state(file_path)
            self.file_selected.emit(file_path)
        else:
            # Show error (could add a toast/notification here)
            print(f"File validation error: {error}")
            
    def clear_file(self) -> None:
        """Clear the selected file."""
        self._selected_file = None
        self._build_empty_state()
        self.file_cleared.emit()
        
    def get_selected_file(self) -> Optional[str]:
        """Get the currently selected file path."""
        return self._selected_file
        
    # =========================================================================
    # Event Handlers
    # =========================================================================
    
    def mousePressEvent(self, event) -> None:
        """Handle mouse click - open file dialog if no file selected."""
        if self._selected_file is None:
            self._open_file_dialog()
        super().mousePressEvent(event)
        
    def _open_file_dialog(self) -> None:
        """Open the file selection dialog."""
        # Build filter string
        extensions = self.accept.replace(',', ' ')
        filter_str = f"Data Files (*{extensions.replace(' ', ' *')});;All Files (*.*)"
        
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Log File",
            "",
            filter_str
        )
        
        if file_path:
            self._handle_file(file_path)
            
    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        """Handle drag enter event."""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self._is_dragging = True
            self.setProperty("class", "drop-zone-active")
            self.style().unpolish(self)
            self.style().polish(self)
            
    def dragLeaveEvent(self, event) -> None:
        """Handle drag leave event."""
        self._is_dragging = False
        self.setProperty("class", "drop-zone")
        self.style().unpolish(self)
        self.style().polish(self)
        
    def dropEvent(self, event: QDropEvent) -> None:
        """Handle file drop event."""
        self._is_dragging = False
        self.setProperty("class", "drop-zone")
        self.style().unpolish(self)
        self.style().polish(self)
        
        # Get dropped files
        urls = event.mimeData().urls()
        if urls:
            file_path = urls[0].toLocalFile()
            self._handle_file(file_path)
            
        event.acceptProposedAction()
