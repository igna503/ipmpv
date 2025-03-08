#!/usr/bin/python
"""MPV player functionality for IPMPV."""

import mpv
import threading
import time
import traceback

class Player:
	"""MPV player wrapper with IPMPV-specific functionality."""
	
	def __init__(self, to_qt_queue):
		"""Initialize the player."""
		self.to_qt_queue = to_qt_queue
		self.player = mpv.MPV(
			log_handler=self.error_check,
			vo='gpu',
			hwdec='auto-safe',
			demuxer_lavf_o='reconnect=1',
			deinterlace='no',
			keepaspect='no',
			geometry='100%:100%',
			fullscreen='yes',
			loop_playlist='inf'
		)
		
		self.deinterlace = False
		self.low_latency = False
		self.current_index = None
		self.vcodec = None
		self.acodec = None
		self.video_res = None
		self.interlaced = None
		
		# Set up property observers
		self.player.observe_property('video-format', self.video_codec_observer)
		self.player.observe_property('audio-codec-name', self.audio_codec_observer)
		
		# Channel change management
		self.channel_change_lock = threading.Lock()
		self.current_channel_thread = None
		self.channel_change_counter = 0  # To track the most recent channel change
	
	def error_check(self, loglevel, component, message):
		"""Check for errors in MPV logs."""
		print(f"[{loglevel}] {component}: {message}")
		if loglevel == 'error' and (component == 'ffmpeg' or component == 'cplayer') and 'Failed' in message:
			self.player.loadfile("./nosignal.png")
			self.to_qt_queue.put({
				'action': 'start_close'
			})
	
	def video_codec_observer(self, name, value):
		"""Observe changes to the video codec."""
		if value:
			self.vcodec = value.upper()
	
	def audio_codec_observer(self, name, value):
		"""Observe changes to the audio codec."""
		if value:
			self.acodec = value.upper()
	
	def play_channel(self, index, channels):
		"""
		Play a channel by index.
		
		Args:
			index (int): Index of the channel to play.
			channels (list): List of channel dictionaries.
		"""

		print(f"\n=== Changing channel to index {index} ===")

		self.vcodec = None
		self.acodec = None

		self.current_index = index % len(channels)
		print(f"Playing channel: {channels[self.current_index]['name']} ({channels[self.current_index]['url']})")
		
		try:
			self.player.loadfile("./novideo.png")
			self.player.wait_until_playing()
			
			channel_info = {
				"name": channels[self.current_index]["name"],
				"deinterlace": self.deinterlace,
				"low_latency": self.low_latency,
				"logo": channels[self.current_index]["logo"]
			}

			self.to_qt_queue.put({
				'action': 'show_osd',
				'channel_info': channel_info
			})


			self.player.loadfile(channels[self.current_index]['url'])
			self.player.wait_until_playing()

			video_params = self.player.video_params
			video_frame_info = self.player.video_frame_info
			if video_params and video_frame_info:
				self.video_res = video_params.get('h')
				self.interlaced = video_frame_info.get('interlaced')
				self.to_qt_queue.put({
					'action': 'update_codecs',
					'vcodec': self.vcodec,
					'acodec': self.acodec,
					'video_res': self.video_res,
					'interlaced': self.interlaced
				})

			self.to_qt_queue.put({
				'action': 'start_close',
			})


		except Exception as e:
				print(f"\033[91mError in play_channel: {str(e)}\033[0m")
				traceback.print_exc()
		
		return
	
	def toggle_deinterlace(self):
		"""Toggle deinterlacing."""
		self.deinterlace = not self.deinterlace
		if self.deinterlace:
			self.player['vf'] = 'yadif=0'
		else:
			self.player['vf'] = ''
		return self.deinterlace
	
	def toggle_latency(self):
		"""Toggle low latency mode."""
		self.low_latency = not self.low_latency
		self.player['audio-buffer'] = '0' if self.low_latency else '0.2'
		self.player['vd-lavc-threads'] = '1' if self.low_latency else '0'
		self.player['cache-pause'] = 'no' if self.low_latency else 'yes'
		self.player['demuxer-lavf-o'] = 'reconnect=1,fflags=+nobuffer' if self.low_latency else 'reconnect=1'
		self.player['demuxer-lavf-probe-info'] = 'nostreams' if self.low_latency else 'auto'
		self.player['demuxer-lavf-analyzeduration'] = '0.1' if self.low_latency else '0'
		self.player['video-sync'] = 'audio'
		self.player['interpolation'] = 'no'
		self.player['video-latency-hacks'] = 'yes' if self.low_latency else 'no'
		self.player['stream-buffer-size'] = '4k' if self.low_latency else '128k'
		return self.low_latency

	def stop(self):
		"""Stop the player."""
		self.player.stop()
		self.current_index = None
