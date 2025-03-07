#!/usr/bin/python
"""On-screen display widget for IPMPV."""

import os
import requests
import traceback
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from utils import is_wayland, osd_corner_radius

class OsdWidget(QWidget):
    """Widget for the on-screen display."""
    
    def __init__(self, channel_info, width=600, height=165, close_time=5, corner_radius=int(osd_corner_radius) if osd_corner_radius is not None else 15):
        """Initialize the OSD widget."""
        QFontDatabase.addApplicationFont('FiraSans-Regular.ttf')
        QFontDatabase.addApplicationFont('FiraSans-Bold.ttf')

        super().__init__()

        self.channel_info = channel_info
        self.orig_width = width
        self.orig_height = height
        self.close_time = close_time
        self.corner_radius = corner_radius
        self.video_codec = None
        self.audio_codec = None
        self.video_res = None
        self.interlaced = None

        # Setup window
        self.setWindowTitle("OSD")
        self.setFixedSize(width, height)

        # Check if we're running on Wayland
        self.is_wayland = is_wayland

        # Set appropriate window flags and size
        if self.is_wayland:
            # For Wayland, use fullscreen transparent approach
            self.setWindowFlags(
                Qt.FramelessWindowHint |
                Qt.WindowStaysOnTopHint
            )

            # Set fullscreen size
            self.screen_geometry = QApplication.desktop().screenGeometry()
            self.setFixedSize(self.screen_geometry.width(), self.screen_geometry.height())

            # Calculate content positioning
            self.content_x = (self.screen_geometry.width() - self.orig_width) // 2
            self.content_y = 20  # 20px from top
        else:
            # For X11, use the original approach
            self.setWindowFlags(
                Qt.FramelessWindowHint |
                Qt.WindowStaysOnTopHint |
                Qt.X11BypassWindowManagerHint |
                Qt.Tool |
                Qt.ToolTip
            )
            self.setFixedSize(width, height)
            self.content_x = 0
            self.content_y = 0

        # Enable transparency
        self.setAttribute(Qt.WA_TranslucentBackground)

        # Position window at the top center of the screen
        self.position_window()

        # Load logo if available
        self.logo_pixmap = None
        if channel_info["logo"]:
            self.load_logo()

        if self.is_wayland:
            self.setAttribute(Qt.WA_TransparentForMouseEvents)

    def position_window(self):
        """Position the window on the screen."""
        if self.is_wayland:
            # For Wayland, we just position at 0,0 (fullscreen)
            self.move(0, 0)

            # Ensure window stays on top
            self.stay_on_top_timer = QTimer(self)
            self.stay_on_top_timer.timeout.connect(lambda: self.raise_())
            self.stay_on_top_timer.start(100)  # Check every 100ms
        else:
            # For X11, center at top
            screen_geometry = QApplication.desktop().screenGeometry()
            x = (screen_geometry.width() - self.orig_width) // 2
            y = 20  # 20px from top
            self.setGeometry(x, y, self.orig_width, self.orig_height)

            # X11 specific window hints
            self.setAttribute(Qt.WA_X11NetWmWindowTypeNotification)
            QTimer.singleShot(100, lambda: self.move(x, y))
            QTimer.singleShot(500, lambda: self.move(x, y))

            # Periodically ensure window stays on top
            self.stay_on_top_timer = QTimer(self)
            self.stay_on_top_timer.timeout.connect(lambda: self.raise_())
            self.stay_on_top_timer.start(1000)  # Check every second

    def load_logo(self):
        """Load the channel logo."""
        try:
            response = requests.get(self.channel_info["logo"])
            if response.ok:
                pixmap = QPixmap()
                pixmap.loadFromData(response.content)
                if not pixmap.isNull():
                    self.logo_pixmap = pixmap.scaled(80, 80, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                    self.update()  # Trigger repaint
        except Exception as e:
            print(f"Failed to load logo: {e}")

    def paintEvent(self, a0):
        """Paint event handler."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        if self.is_wayland:
            # For Wayland, we're drawing the content in the right position on a fullscreen widget
            self.draw_osd_content(painter, self.content_x, self.content_y)
        else:
            # For X11, we're drawing directly at (0,0) since the widget is already positioned
            self.draw_osd_content(painter, 0, 0)
            
    def draw_osd_content(self, painter, x_offset, y_offset):
        """Draw the OSD content."""
        # Create a path for rounded rectangle background
        path = QPainterPath()
        path.addRoundedRect(
            x_offset, y_offset,
            self.orig_width, self.orig_height,
            self.corner_radius, self.corner_radius
        )

        # Fill the rounded rectangle with semi-transparent background
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(0, 50, 100, 200))  # RGBA
        painter.drawPath(path)

        # Setup text drawing
        painter.setPen(QColor(255, 255, 255))

        try:
            font = QFont("Fira Sans", 18)
            font.setBold(True)
            painter.setFont(font)

            # Draw channel name
            painter.drawText(x_offset + 20, y_offset + 40, self.channel_info["name"])

            font.setPointSize(14)
            font.setBold(False)
            painter.setFont(font)

            # Draw deinterlace status
            painter.drawText(x_offset + 20, y_offset + 70, f"Deinterlacing {'on' if self.channel_info['deinterlace'] else 'off'}")

            # Draw latency mode
            painter.drawText(x_offset + 20, y_offset + 100, f"{'Low' if self.channel_info['low_latency'] else 'High'} latency")

            # Draw codec badges if available
            if self.video_codec:
                self.draw_badge(painter, self.video_codec, x_offset + 80, y_offset + self.orig_height - 40)
            if self.audio_codec:
                self.draw_badge(painter, self.audio_codec, x_offset + 140, y_offset + self.orig_height - 40)
            if self.video_res:
                self.draw_badge(painter, f"{self.video_res}{self.interlaced if self.interlaced is not None else ''}", x_offset + 20, y_offset + self.orig_height - 40)
            # Draw logo if available
            if self.logo_pixmap:
                painter.drawPixmap(x_offset + self.orig_width - 100, y_offset + 20, self.logo_pixmap)

        except Exception as e:
            print(f"Error in painting: {e}")
            traceback.print_exc()

    def draw_badge(self, painter, text, x, y):
        """Draw a badge with text."""
        # Save current painter state
        painter.save()

        # Draw rounded badge
        painter.setPen(QPen(QColor(255, 255, 255, 255), 2))
        painter.setBrush(Qt.NoBrush)

        # Use QPainterPath for consistent rounded corners
        badge_path = QPainterPath()
        badge_path.addRoundedRect(x, y, 48, 20, 7, 7)
        painter.drawPath(badge_path)

        # Draw text
        painter.setPen(QColor(255, 255, 255))
        font = painter.font()
        font.setBold(True)
        font.setPointSize(8)
        painter.setFont(font)

        # Center text in badge
        font_metrics = painter.fontMetrics()
        text_width = font_metrics.width(text)
        text_height = font_metrics.height()

        # We need to use integer coordinates for drawText, not floats
        text_x = int(x + (48 - text_width) / 2)
        text_y = int(y + text_height)

        # Use the int, int, string version of drawText
        painter.drawText(text_x, text_y, text)

        # Restore painter state
        painter.restore()

    def update_codecs(self, video_codec, audio_codec, video_res, interlaced):
        """Update codec information."""
        if video_codec:
            self.video_codec = video_codec
        if audio_codec:
            self.audio_codec = audio_codec
        if video_res:
            self.video_res = video_res
        if interlaced is not None:
            self.interlaced = f"{'i' if interlaced else 'p'}"
        self.update()  # Trigger repaint

    def close_widget(self):
        """Close the widget."""
        # Stop any active timers
        if hasattr(self, 'stay_on_top_timer') and self.stay_on_top_timer.isActive():
            self.stay_on_top_timer.stop()
        # Close the widget
        self.hide()

    def start_close_timer(self, seconds=5):
        """Start a timer to close the widget."""
        # Cancel any existing close timer
        if hasattr(self, 'close_timer') and self.close_timer.isActive():
            self.close_timer.stop()

        # Create and start a new timer
        self.close_timer = QTimer(self)
        self.close_timer.setSingleShot(True)
        self.close_timer.timeout.connect(self.close_widget)
        self.close_timer.start(seconds * 1000)  # Convert seconds to milliseconds
