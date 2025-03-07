#!/usr/bin/python
"""Qt process for IPMPV OSD."""

import sys
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QTimer
from osd import OsdWidget
from volume_osd import VolumeOsdWidget
from utils import is_wayland

def qt_process(to_qt_queue, from_qt_queue):
	"""
	Run Qt application in a separate process.
	
	Args:
		to_qt_queue: Queue for messages to Qt process
		from_qt_queue: Queue for messages from Qt process
	"""
	app = QApplication(sys.argv)
	osd = None
	volume_osd = None

	# Check the queue periodically for commands
	def check_queue():
		nonlocal osd, volume_osd
		if not to_qt_queue.empty():
			command = to_qt_queue.get()
			
			# Channel OSD commands
			if command['action'] == 'show_osd':
				if osd is not None:
					osd.close_widget()
				# Create new OSD
				osd = OsdWidget(command['channel_info'])
				if is_wayland:
					osd.showFullScreen()
				else:
					osd.show()
			elif command['action'] == 'start_close':
				if osd is not None:
					osd.start_close_timer()
			elif command['action'] == 'close_osd':
				if osd is not None:
					osd.close_widget()
					osd = None
			elif command['action'] == 'update_codecs':
				if osd is not None:
					osd.update_codecs(command['vcodec'], command['acodec'], command['video_res'], command['interlaced'])
			
			# Volume OSD commands
			elif command['action'] == 'show_volume_osd' or command['action'] == 'update_volume_osd':
				# Get volume level and mute state
				volume_level = command.get('volume_level', 0)
				is_muted = command.get('is_muted', False)
				
				# If muted, override volume display to 0
				display_volume = 0 if is_muted else volume_level
				
				# Update existing volume OSD if present, otherwise create new one
				if volume_osd is not None and volume_osd.isVisible():
					volume_osd.update_volume(display_volume)
					volume_osd.start_close_timer()
				else:
					# Create new volume OSD if none exists or if it's not visible
					if volume_osd is not None:
						volume_osd.close_widget()
					
					volume_osd = VolumeOsdWidget(display_volume)
					if is_wayland:
						volume_osd.showFullScreen()
					else:
						volume_osd.show()
					
					# Start the close timer
					volume_osd.start_close_timer()
			elif command['action'] == 'close_volume_osd':
				if volume_osd is not None:
					volume_osd.close_widget()
					volume_osd = None
					
		# Schedule next check
		QTimer.singleShot(100, check_queue)

	# Start the queue check
	check_queue()

	# Run Qt event loop
	app.exec_()
