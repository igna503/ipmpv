#!/usr/bin/python
"""Flask server for IPMPV."""

import os
import re
import subprocess
import threading
import flask
from flask import request, jsonify, send_from_directory, session, redirect, url_for
from localization import localization, _
from utils import is_valid_url, change_resolution, get_current_resolution, is_wayland, get_or_create_secret_key

class IPMPVServer:
	"""Flask server for IPMPV web interface."""

	def __init__(self, channels, player, to_qt_queue, from_qt_queue, resolution, ipmpv_retroarch_cmd, volume_control=None):
		"""Initialize the server."""
		self.app = flask.Flask(__name__,
							  static_folder='static',
							  template_folder='templates')
		self.channels = channels
		self.player = player
		self.to_qt_queue = to_qt_queue
		self.from_qt_queue = from_qt_queue
		self.resolution = resolution
		self.ipmpv_retroarch_cmd = ipmpv_retroarch_cmd
		self.retroarch_p = None
		self.volume_control = volume_control
		self.app.secret_key = get_or_create_secret_key()

		# Register routes
		self._register_routes()


	def run(self, host="0.0.0.0", port=5000):
		"""Run the Flask server."""
		self.app.run(host=host, port=port)
	def _register_routes(self):
		"""Register Flask routes."""

		@self.app.route("/switch_language/<language>")
		def switch_language(language):
			localization.set_language(language)
			return redirect(request.referrer or url_for('index'))

		@self.app.route("/")
		def index():
			return self._handle_index()

		@self.app.route("/play_custom")
		def play_custom():
			return self._handle_play_custom()

		@self.app.route("/hide_osd")
		def hide_osd():
			return self._handle_hide_osd()

		@self.app.route("/show_osd")
		def show_osd():
			return self._handle_show_osd()

		@self.app.route("/channel")
		def switch_channel():
			return self._handle_switch_channel()

		@self.app.route("/toggle_deinterlace")
		def toggle_deinterlace():
			return self._handle_toggle_deinterlace()

		@self.app.route("/stop_player")
		def stop_player():
			return self._handle_stop_player()

		@self.app.route("/toggle_retroarch")
		def toggle_retroarch():
			return self._handle_toggle_retroarch()

		@self.app.route("/toggle_latency")
		def toggle_latency():
			return self._handle_toggle_latency()

		@self.app.route("/toggle_resolution")
		def toggle_resolution():
			return self._handle_toggle_resolution()

		@self.app.route("/volume_up")
		def volume_up():
			return self._handle_volume_up()

		@self.app.route("/volume_down")
		def volume_down():
			return self._handle_volume_down()

		@self.app.route("/toggle_mute")
		def toggle_mute():
			return self._handle_toggle_mute()

		@self.app.route("/channel_up")
		def channel_up():
			return self._handle_channel_up()

		@self.app.route("/channel_down")
		def channel_down():
			return self._handle_channel_down()

		@self.app.route('/manifest.json')
		def serve_manifest():
			return send_from_directory("static", 'manifest.json',
								  mimetype='application/manifest+json')

		@self.app.route('/icon512_rounded.png')
		def serve_rounded_icon():
			return send_from_directory("static", 'icon512_rounded.png',
								  mimetype='image/png')

		@self.app.route('/icon512_maskable.png')
		def serve_maskable_icon():
			return send_from_directory("static", 'icon512_maskable.png',
								  mimetype='image/png')

		@self.app.route('/screenshot1.png')
		def serve_screenshot_1():
			return send_from_directory("static", 'screenshot1.png',
								  mimetype='image/png')

		@self.app.route('/favicon.ico')
		def serve_favicon():
			return send_from_directory("static", 'favicon.ico',
								  mimetype='image/vnd.microsoft.icon')
	def _handle_index(self):
		"""Handle the index route."""
		from channels import group_channels
		
		grouped_channels = group_channels(self.channels)
		flat_channel_list = [channel for channel in self.channels]
		
		# Create the channel groups HTML
		channel_groups_html = ""
		for group, ch_list in grouped_channels.items():
			# Translate group name if it's a common group
			translated_group = _(group.lower()) if group.lower() in ["other"] else group
			channel_groups_html += f'<div class="group">{translated_group}'
			for channel in ch_list:
				index = flat_channel_list.index(channel)  # Get correct global index
				channel_groups_html += f'''
					<div class="channel">
						<img src="{channel['logo']}" onerror="this.style.display='none'">
						<button onclick="changeChannel({index})">{channel['name']}</button>
					</div>
				'''
			channel_groups_html += '</div>'
		
		# Get current language and available languages for language selector
		current_language = localization.get_language()
		languages = {
			'en': 'English',
			'es': 'Español'
			# Add more languages here as you support them
		}
		
		language_selector_html = ""
		for code, name in languages.items():
			selected = ' selected' if code == current_language else ''
			language_selector_html += f'<option value="{code}"{selected}>{name}</option>'
		
		# Replace placeholders with actual values, using translation
		html = open("templates/index.html").read()
		html = html.replace("%WELCOME_TEXT%", _("welcome_to_ipmpv"))
		html = html.replace("%CURRENT_CHANNEL_LABEL%", _("current_channel"))
		html = html.replace("%CURRENT_CHANNEL%", 
						  self.channels[self.player.current_index]['name'] 
						  if self.player.current_index is not None else "None")
		html = html.replace("%RETROARCH_STATE%", 
						  "ON" if self.retroarch_p and self.retroarch_p.poll() is None else "OFF")
		html = html.replace("%RETROARCH_LABEL%", 
						  _("stop_retroarch") if self.retroarch_p and self.retroarch_p.poll() is None else _("start_retroarch"))
		html = html.replace("%DEINTERLACE_LABEL%", _("deinterlacing"))
		html = html.replace("%DEINTERLACE_STATE%", _("on") if self.player.deinterlace else _("off"))
		html = html.replace("%RESOLUTION_LABEL%", _("resolution"))
		html = html.replace("%RESOLUTION%", self.resolution)
		html = html.replace("%LATENCY_STATE%", "ON" if self.player.low_latency else "OFF")
		html = html.replace("%LATENCY_LABEL%", _("latency_low") if self.player.low_latency else _("latency_high"))
		html = html.replace("%CHANNEL_GROUPS%", channel_groups_html)
		html = html.replace("%VOLUME_LABEL%", _("volume"))
		html = html.replace("%MUTE_LABEL%", _("mute"))
		html = html.replace("%TOGGLE_OSD_LABEL%", _("toggle_osd"))
		html = html.replace("%ON_LABEL%", _("on"))
		html = html.replace("%OFF_LABEL%", _("off"))
		html = html.replace("%PLAY_CUSTOM_URL_LABEL%", _("play_custom_url"))
		html = html.replace("%ENTER_URL_PLACEHOLDER%", _("enter_stream_url"))
		html = html.replace("%PLAY_LABEL%", _("play"))
		html = html.replace("%ALL_CHANNELS_LABEL%", _("all_channels"))
		html = html.replace("%STOP_LABEL%", _("stop"))
		html = html.replace("%LANGUAGE_SELECTOR%", language_selector_html)
		
		return html

	def _handle_play_custom(self):
		"""Handle the play_custom route."""
		url = request.args.get("url")

		if not url or not is_valid_url(url):
			return jsonify(success=False, error=_("invalid_url"))

		self.player.player.loadfile(url)
		self.player.current_index = None
		return jsonify(success=True)

	def _handle_hide_osd(self):
		"""Handle the hide_osd route."""
		self.to_qt_queue.put({
			'action': 'close_osd',
		})
		return "", 204

	def _handle_show_osd(self):
		"""Handle the show_osd route."""
		if self.player.current_index is not None:
			channel_info = {
				"name": self.channels[self.player.current_index]["name"],
				"deinterlace": self.player.deinterlace,
				"low_latency": self.player.low_latency,
				"logo": self.channels[self.player.current_index]["logo"]
			}
			self.to_qt_queue.put({
				'action': 'show_osd',
				'channel_info': channel_info
			})
			self.to_qt_queue.put({
				'action': 'update_codecs',
				'vcodec': self.player.vcodec,
				'acodec': self.player.acodec,
				'video_res': self.player.video_res,
				'interlaced': self.player.interlaced
			})
		return "", 204

	def _handle_switch_channel(self):
		"""Handle the switch_channel route."""
		self.player.stop()
		index = int(request.args.get("index", self.player.current_index))
		thread = threading.Thread(
			target=self.player.play_channel,
			args=(index,self.channels),
			daemon=True
		)
		thread.start()
		return "", 204

	def _handle_channel_up(self):
		"""Handle the channel_up route."""
		index = self.player.current_index + 1 if self.player.current_index is not None else 0;
		thread = threading.Thread(
			target=self.player.play_channel,
			args=(index,self.channels),
			daemon=True
		)
		thread.start()
		return "", 204

	def _handle_channel_down(self):
		"""Handle the channel_down route."""
		index = self.player.current_index - 1 if self.player.current_index is not None else -1;
		thread = threading.Thread(
			target=self.player.play_channel,
			args=(index,self.channels),
			daemon=True
		)
		thread.start()
		return "", 204

	def _handle_toggle_deinterlace(self):
		"""Handle the toggle_deinterlace route."""
		state = self.player.toggle_deinterlace()
		return jsonify(state=state)

	def _handle_stop_player(self):
		"""Handle the stop_player route."""
		self.to_qt_queue.put({
			'action': 'close_osd',
		})
		self.player.stop()
		return "", 204

	def _handle_toggle_retroarch(self):
		"""Handle the toggle_retroarch route."""
		retroarch_pid = subprocess.run(["pgrep", "-fx", "retroarch"], stdout=subprocess.PIPE).stdout.strip()
		if retroarch_pid:
			print("Retroarch already open. Trying to close it.")
			subprocess.run(["kill", retroarch_pid])
			if self.retroarch_p:
				self.retroarch_p.terminate()
			return jsonify(state=False)
		else:
			print("Launching RetroArch")
			retroarch_env = os.environ.copy()
			retroarch_env["MESA_GL_VERSION_OVERRIDE"] = "3.3"
			self.retroarch_p = subprocess.Popen(re.split("\\s", self.ipmpv_retroarch_cmd
													   if self.ipmpv_retroarch_cmd is not None
													   else 'retroarch'), env=retroarch_env)
			return jsonify(state=True)

	def _handle_toggle_latency(self):
		"""Handle the toggle_latency route."""
		state = self.player.toggle_latency()
		return jsonify(state=state)

	def _handle_toggle_resolution(self):
		"""Handle the toggle_resolution route."""
		self.resolution = change_resolution(self.resolution)
		return jsonify(res=self.resolution)

	def _handle_volume_up(self):
		"""Handle the volume_up route."""
		if self.volume_control:
			step = request.args.get("step")
			step = int(step) if step and step.isdigit() else None
			new_volume = self.volume_control.volume_up(step)
			return jsonify(volume=new_volume, muted=self.volume_control.is_muted())
		return jsonify(error="Volume control not available"), 404

	def _handle_volume_down(self):
		"""Handle the volume_down route."""
		if self.volume_control:
			step = request.args.get("step")
			step = int(step) if step and step.isdigit() else None
			new_volume = self.volume_control.volume_down(step)
			return jsonify(volume=new_volume, muted=self.volume_control.is_muted())
		return jsonify(error="Volume control not available"), 404

	def _handle_toggle_mute(self):
		"""Handle the toggle_mute route."""
		if self.volume_control:
			is_muted = self.volume_control.toggle_mute()
			volume = self.volume_control.get_volume()
			return jsonify(muted=is_muted, volume=volume)
		return jsonify(error="Volume control not available"), 404

	def _handle_get_volume(self):
		"""Handle the get_volume route."""
		if self.volume_control:
			volume = self.volume_control.get_volume()
			is_muted = self.volume_control.is_muted()
			return jsonify(volume=volume, muted=is_muted)
		return jsonify(error="Volume control not available"), 404
