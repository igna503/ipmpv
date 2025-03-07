#!/usr/bin/python
"""Entry point for IPMPV."""

import multiprocessing
from multiprocessing import Queue
import sys

# Set up utils first
from utils import setup_environment, get_current_resolution, ipmpv_retroarch_cmd

# Initialize environment
setup_environment()

# Set up channel data
from channels import get_channels

# Import remaining modules
from player import Player
from server import IPMPVServer
from qt_process import qt_process
from volume import VolumeControl

def main():
	"""Main entry point for IPMPV."""
	# Create communication queues
	to_qt_queue = Queue()
	from_qt_queue = Queue()
	
	# Get initial data
	channels = get_channels()
	resolution = get_current_resolution()
	
	# Initialize player
	player = Player(to_qt_queue)

	# Initialize volume control
	volume_control = VolumeControl(to_qt_queue=to_qt_queue)
	
	# Start Qt process
	qt_proc = multiprocessing.Process(
		target=qt_process,
		args=(to_qt_queue, from_qt_queue),
		daemon=True
	)
	qt_proc.start()
	
	# Start Flask server
	server = IPMPVServer(
		channels=channels,
		player=player,
		to_qt_queue=to_qt_queue,
		from_qt_queue=from_qt_queue,
		resolution=resolution,
		ipmpv_retroarch_cmd=ipmpv_retroarch_cmd,
		volume_control=volume_control
	)
	
	try:
		# Run the Flask server (this will block)
		server.run(host="0.0.0.0", port=5000)
	except KeyboardInterrupt:
		print("Shutting down...")
	finally:
		# Clean up
		if qt_proc.is_alive():
			qt_proc.terminate()
			qt_proc.join(timeout=1)
		sys.exit(0)

if __name__ == "__main__":
	main()
