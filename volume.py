#!/usr/bin/python
"""Alsa volume control functions for IPMPV."""

import subprocess
import alsaaudio
import threading
import traceback
import time

class VolumeControl:
	"""
	Class for controlling audio volume with ALSA.
	
	This class provides an interface to control the volume with PyAlsa,
	with methods to get current volume, increase/decrease volume, 
	and toggle mute.
	"""
	
	def __init__(self, mixer_name='Master', step=5, to_qt_queue=None):
		"""
		Initialize the volume control.
		
		Args:
			mixer_name (str): Name of the ALSA mixer to control
			step (int): Default step size for volume increments
			to_qt_queue: Queue for sending messages to Qt process for OSD
		"""
		self.mixer_name = mixer_name
		self.step = step
		self.to_qt_queue = to_qt_queue
		self.volume_thread = None
		self.volume_lock = threading.Lock()
		self._init_mixer()
		
	def _init_mixer(self):
		"""Initialize the ALSA mixer."""
		try:
			# Try to get the requested mixer
			self.mixer = alsaaudio.Mixer(self.mixer_name)
			print(f"Successfully initialized ALSA mixer: {self.mixer_name}")
		except alsaaudio.ALSAAudioError as e:
			print(f"Error initializing mixer '{self.mixer_name}': {e}")
			# Try to get a list of available mixers
			available_mixers = alsaaudio.mixers()
			print(f"Available mixers: {available_mixers}")
			
			# Try some common alternatives
			fallback_mixers = ['PCM', 'Speaker', 'Master', 'Front', 'Headphone']
			for mixer in fallback_mixers:
				if mixer in available_mixers:
					try:
						self.mixer = alsaaudio.Mixer(mixer)
						self.mixer_name = mixer
						print(f"Using fallback mixer: {mixer}")
						return
					except alsaaudio.ALSAAudioError:
						continue
			
			# If we still don't have a mixer, raise an exception
			raise Exception("Could not find a suitable ALSA mixer")
	
	def get_volume(self):
		"""
		Get the current volume level.
		
		Returns:
			int: Current volume as a percentage (0-100)
		"""
		try:
			# Get all channels and average them
			volumes = self.mixer.getvolume()
			return sum(volumes) // len(volumes)
		except Exception as e:
			print(f"Error getting volume: {e}")
			traceback.print_exc()
			return 0
	
	def is_muted(self):
		"""
		Check if audio is muted.
		
		Returns:
			bool: True if muted, False otherwise
		"""
		try:
			# Get mute state for all channels (returns list of 0/1 values)
			mutes = self.mixer.getmute()
			# If any channel is muted (1), consider it muted
			return any(mute == 1 for mute in mutes)
		except Exception as e:
			print(f"Error checking mute state: {e}")
			traceback.print_exc()
			return False
	
	def volume_up(self, step=None):
		"""
		Increase volume.
		
		Args:
			step (int, optional): Amount to increase volume by. Defaults to self.step.
			
		Returns:
			int: New volume level
		"""
		return self._adjust_volume(step if step is not None else self.step)
	
	def volume_down(self, step=None):
		"""
		Decrease volume.
		
		Args:
			step (int, optional): Amount to decrease volume by. Defaults to self.step.
			
		Returns:
			int: New volume level
		"""
		return self._adjust_volume(-(step if step is not None else self.step))
	
	def toggle_mute(self):
		"""
		Toggle mute state.
		
		Returns:
			bool: New mute state
		"""
		try:
			muted = self.is_muted()
			# Set all channels to the opposite of current mute state
			self.mixer.setmute(0 if muted else 1)
			
			new_mute_state = not muted
			
			# Update OSD if queue is available
			if self.to_qt_queue is not None:
				self.to_qt_queue.put({
					'action': 'show_volume_osd',
					'volume_level': 0 if new_mute_state else self.get_volume(),
					'is_muted': new_mute_state
				})
			
			return new_mute_state
		except Exception as e:
			print(f"Error toggling mute: {e}")
			traceback.print_exc()
			return self.is_muted()
	
	def _adjust_volume(self, change):
		"""
		Internal method to adjust volume.
		
		Args:
			change (int): Amount to change volume by (positive or negative)
			
		Returns:
			int: New volume level
		"""
		with self.volume_lock:
			try:
				current = self.get_volume()
				new_volume = max(0, min(100, current + change))
				
				# Set new volume on all channels
				self.mixer.setvolume(new_volume)
				
				# If we were muted and increasing volume, unmute
				if change > 0 and self.is_muted():
					self.mixer.setmute(0)
				
				# Update OSD if queue is available
				if self.to_qt_queue is not None:
					self.to_qt_queue.put({
						'action': 'show_volume_osd',
						'volume_level': new_volume,
						'is_muted': False
					})
				
				return new_volume
			except Exception as e:
				print(f"Error adjusting volume: {e}")
				traceback.print_exc()
				return self.get_volume()
