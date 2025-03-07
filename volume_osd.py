#!/usr/bin/python
"""Volume on-screen display widget for IPMPV."""

import os
import traceback
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from utils import is_wayland, osd_corner_radius

class VolumeOsdWidget(QWidget):
	"""Widget for the volume on-screen display."""
	
	def __init__(self, volume_level, width=300, height=80, close_time=2, corner_radius=int(osd_corner_radius) if osd_corner_radius is not None else 15):
		"""
		Initialize the volume OSD widget.
		
		Args:
			volume_level (int): Current volume level (0-100)
			width (int): Width of the widget
			height (int): Height of the widget
			close_time (int): Time in seconds before the widget closes
			corner_radius (int): Corner radius for the widget
		"""
		QFontDatabase.addApplicationFont('FiraSans-Regular.ttf')
		QFontDatabase.addApplicationFont('FiraSans-Bold.ttf')

		super().__init__()

		self.volume_level = volume_level
		self.orig_width = width
		self.orig_height = height
		self.close_time = close_time
		self.corner_radius = corner_radius

		# Setup window
		self.setWindowTitle("Volume OSD")
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
			self.content_y = self.screen_geometry.height() - self.orig_height - 20  # 20px from bottom
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

		# Position window at the bottom center of the screen
		self.position_window()

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
			# For X11, center at bottom
			screen_geometry = QApplication.desktop().screenGeometry()
			x = (screen_geometry.width() - self.orig_width) // 2
			y = screen_geometry.height() - self.orig_height - 20  # 20px from bottom
			self.setGeometry(x, y, self.orig_width, self.orig_height)

			# X11 specific window hints
			self.setAttribute(Qt.WA_X11NetWmWindowTypeNotification)
			QTimer.singleShot(100, lambda: self.move(x, y))
			QTimer.singleShot(500, lambda: self.move(x, y))

			# Periodically ensure window stays on top
			self.stay_on_top_timer = QTimer(self)
			self.stay_on_top_timer.timeout.connect(lambda: self.raise_())
			self.stay_on_top_timer.start(1000)  # Check every second

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
		try:
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

			# Draw volume icon or symbol
			font = QFont("Fira Sans", 14)
			font.setBold(True)
			painter.setFont(font)
			
			# Draw volume label
			painter.drawText(x_offset + 20, y_offset + 30, "Volume")
			
			# Draw volume value
			font.setPointSize(12)
			painter.setFont(font)
			volume_text = f"{self.volume_level}%"
			painter.drawText(x_offset + self.orig_width - 60, y_offset + 30, volume_text)
			
			# Draw volume bar background
			bar_x = x_offset + 20
			bar_y = y_offset + 40
			bar_width = self.orig_width - 40
			bar_height = 16
			
			bg_path = QPainterPath()
			bg_path.addRoundedRect(bar_x, bar_y, bar_width, bar_height, 8, 8)
			painter.setPen(Qt.NoPen)
			painter.setBrush(QColor(255, 255, 255, 70))
			painter.drawPath(bg_path)
			
			# Draw volume level fill
			if self.volume_level > 0:
				fill_width = int((bar_width * self.volume_level) / 100)
				fill_path = QPainterPath()
				fill_path.addRoundedRect(bar_x, bar_y, fill_width, bar_height, 8, 8)
				
				# Determine color based on volume level
				if self.volume_level <= 30:
					fill_color = QColor(0, 200, 83)  # Green
				elif self.volume_level <= 70:
					fill_color = QColor(255, 193, 7)  # Yellow/Amber
				else:
					fill_color = QColor(255, 87, 34)  # Red/Orange
				
				painter.setBrush(fill_color)
				painter.drawPath(fill_path)
			
		except Exception as e:
			print(f"Error in painting volume OSD: {e}")
			traceback.print_exc()

	def update_volume(self, volume_level):
		"""Update the volume level displayed in the OSD."""
		self.volume_level = volume_level
		self.update()  # Trigger repaint

	def close_widget(self):
		"""Close the widget."""
		# Stop any active timers
		if hasattr(self, 'stay_on_top_timer') and self.stay_on_top_timer.isActive():
			self.stay_on_top_timer.stop()
		# Close the widget
		self.hide()

	def start_close_timer(self, seconds=None):
		"""Start a timer to close the widget."""
		# Use the provided seconds or default to self.close_time
		seconds = seconds if seconds is not None else self.close_time
		
		# Cancel any existing close timer
		if hasattr(self, 'close_timer') and self.close_timer.isActive():
			self.close_timer.stop()

		# Create and start a new timer
		self.close_timer = QTimer(self)
		self.close_timer.setSingleShot(True)
		self.close_timer.timeout.connect(self.close_widget)
		self.close_timer.start(seconds * 1000)  # Convert seconds to milliseconds
