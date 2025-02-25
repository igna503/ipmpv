#!/usr/bin/python
import sys
import mpv
import requests
import flask
import re
import subprocess
import os
import time
import multiprocessing

from flask import request
from flask import jsonify

from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *

from multiprocessing import Queue

os.environ["LC_ALL"] = "C"
os.environ["LANG"] = "C"

is_wayland = "WAYLAND_DISPLAY" in os.environ
osd_corner_radius = os.environ.get("IPMPV_CORNER_RADIUS")
ipmpv_retroarch_cmd = os.environ.get("IPMPV_RETROARCH_CMD")

to_qt_queue = Queue()
from_qt_queue = Queue()

M3U_URL = os.environ.get('IPMPV_M3U_URL')

class OsdWidget(QWidget):
	def __init__(self, channel_info, width=600, height=165, close_time=5, corner_radius=int(osd_corner_radius) if osd_corner_radius is not None else 15):

		QFontDatabase.addApplicationFont('FiraSans-Regular.ttf')
		QFontDatabase.addApplicationFont('FiraSans-Bold.ttf')

		global is_wayland
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
				Qt.WindowStaysOnTopHint |
				Qt.WindowDoesNotAcceptFocus
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
		if self.is_wayland:
			# For Wayland, we just position at 0,0 (fullscreen)
			self.move(0, 0)

			# Ensure window stays on top
			self.stay_on_top_timer = QTimer(self)
			self.stay_on_top_timer.timeout.connect(lambda: self.raise_())
			self.stay_on_top_timer.start(100)  # Check every second
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
		painter = QPainter(self)
		painter.setRenderHint(QPainter.Antialiasing)

		if self.is_wayland:
			# For Wayland, we're drawing the content in the right position on a fullscreen widget
			self.draw_osd_content(painter, self.content_x, self.content_y)
		else:
			# For X11, we're drawing directly at (0,0) since the widget is already positioned
			self.draw_osd_content(painter, 0, 0)
	def draw_osd_content(self, painter, x_offset, y_offset):
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
			import traceback
			traceback.print_exc()

	def draw_badge(self, painter, text, x, y):
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
		# Stop any active timers
		if hasattr(self, 'stay_on_top_timer') and self.stay_on_top_timer.isActive():
			self.stay_on_top_timer.stop()
		# Close the widget
		self.hide()

	def start_close_timer(self, seconds=5):
		"""
		Starts a timer to close the widget after the specified number of seconds.

		Parameters:
		seconds (int): Number of seconds before closing the widget (default: 3)
		"""
		# Cancel any existing close timer
		if hasattr(self, 'close_timer') and self.close_timer.isActive():
			self.close_timer.stop()

		# Create and start a new timer
		self.close_timer = QTimer(self)
		self.close_timer.setSingleShot(True)
		self.close_timer.timeout.connect(self.close_widget)
		self.close_timer.start(seconds * 1000)  # Convert seconds to milliseconds

osd = None

def qt_process():
	"""Run Qt application in a separate process"""
	from PyQt5.QtWidgets import QApplication
	from PyQt5.QtCore import QTimer

	app = QApplication(sys.argv)
	osd = None

	# Check the queue periodically for commands

	def check_queue():
		global osd
		if not to_qt_queue.empty():
			command = to_qt_queue.get()
			if command['action'] == 'show_osd':
				if osd is not None:
					osd.close_widget()
				# Create new OSD
				osd = OsdWidget(command['channel_info'])
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
		# Schedule next check
		QTimer.singleShot(100, check_queue)

	# Start the queue check
	check_queue()

	# Run Qt event loop
	app.exec_()

def get_channels():
	if M3U_URL:
		response = requests.get(M3U_URL)
	else:
		print("Error: IPMPV_M3U_URL not set. Please set this environment variable to the URL of your IPTV list, in M3U format.")
		exit(1)
	lines = response.text.splitlines()

	channels = []
	regex = re.compile(r'tvg-logo="(.*?)".*?group-title="(.*?)"', re.IGNORECASE)

	for i in range(len(lines)):
		if lines[i].startswith("#EXTINF"):
			match = regex.search(lines[i])
			logo = match.group(1) if match else ""
			group = match.group(2) if match else "Other"
			name = lines[i].split(",")[-1]
			url = lines[i + 1]

			channels.append({"name": name, "url": url, "logo": logo, "group": group})

	return channels

def get_current_resolution():
	global is_wayland
	try:
		if is_wayland:
			wlr_randr_env = os.environ.copy()
			output = subprocess.check_output(["wlr-randr"], universal_newlines=True, env=wlr_randr_env)
			if "Composite-1" in output.split("\n")[0]:
				for line in output.split("\n"):
						if "720x480" in line and "current" in line:
							return "480i"
						elif "720x240" in line and "current" in line:
							return "240p"
						elif "720x576" in line and "current" in line:
							return "576i"
						elif "720x288" in line and "current" in line:
							return "288p"
		else:
			xrandr_env = os.environ.copy()
			output = subprocess.check_output(["xrandr"], universal_newlines=True, env=xrandr_env)
			for line in output.split("\n"):
				if "Composite-1" in line:
					if "720x480" in line:
						return "480i"
					elif "720x240" in line:
						return "240p"
					elif "720x576" in line:
						return "576i"
					elif "720x288" in line:
						return "288p"
	except subprocess.CalledProcessError:
		if is_wayland:
			print("Error: Cannot get display resolution. Is this a wl-roots compatible compositor?")
		else:
			print("Error: Cannot get display resolution. Is an X session running?")
	except FileNotFoundError:
		if is_wayland:
			print("Error: Could not find wlr-randr, resolution will be unknown")
		else:
			print("Error: Could not find xrandr, resolution will be unknown")
	return "UNK"

def error_check(loglevel, component, message):
	global player
	print(f"[{loglevel}] {component}: {message}")
	if loglevel == 'error' and (component == 'ffmpeg' or component == 'cplayer') and 'Failed' in message:
		player.loadfile("./nosignal.png")
		to_qt_queue.put({
			'action': 'start_close'
		})

player = mpv.MPV(
	# it's a bit weird that i have to use the logs to get errors,
	# but catch_errors is apparently broken
	log_handler = error_check,
	vo = 'gpu',
	hwdec = 'auto-safe',
	demuxer_lavf_o = 'reconnect=1',
	deinterlace = 'no',
	keepaspect = 'no',
	geometry = '100%:100%',
	fullscreen = 'yes',
	loop_playlist = 'inf'
)
deinterlace = False
channels = get_channels()
current_index = None
retroarch_p = None
resolution = get_current_resolution()
low_latency = False
vcodec = None
acodec = None
video_res = None
interlaced = None

@player.property_observer('video-format')
def video_codec_observer(name, value):
	global vcodec, acodec
	if value:
		vcodec = value.upper()

@player.property_observer('audio-codec-name')
def audio_codec_observer(name, value):
	global acodec, vcodec
	if value:
		acodec = value.upper()

def play_channel(index):
	global current_index, vcodec, acodec, video_res, interlaced
	print(f"\n=== Starting channel change to index {index} ===")

	to_qt_queue.put({
		'action': 'close_osd'
	})
	print("Closed OSD")

	vcodec = None
	acodec = None
	current_index = index % len(channels)
	print(f"Playing channel: {channels[current_index]['name']} ({channels[current_index]['url']})")

	try:
		player.loadfile("./novideo.png")
		player.wait_until_playing()

		channel_info = {
			"name": channels[current_index]["name"],
			"deinterlace": deinterlace,
			"low_latency": low_latency,
			"logo": channels[current_index]["logo"]
		}

		to_qt_queue.put({
			'action': 'show_osd',
			'channel_info': channel_info
		})

		player.loadfile(channels[current_index]['url'])
		time.sleep(0.5)
		player.wait_until_playing()

		video_params = player.video_params
		video_frame_info = player.video_frame_info
		if video_params and video_frame_info:
			video_res = video_params.get('h')
			interlaced = video_frame_info.get('interlaced')
			to_qt_queue.put({
							'action': 'update_codecs',
							'vcodec': vcodec,
							'acodec': acodec,
							'video_res': video_res,
							'interlaced': interlaced
			})

		to_qt_queue.put({
				'action': 'start_close',
		})

	except Exception as e:
		print(f"\033[91mError in play_channel: {str(e)}\033[0m")
		traceback.print_exc()

app = flask.Flask(__name__)
# Flask routes here

@app.route("/")
def index():
	grouped_channels = {}
	for channel in channels:
		grouped_channels.setdefault(channel["group"], []).append(channel)

	flat_channel_list = [channel for channel in channels]

	html = f"""
	<html>
	<head>
		<title>IPMPV</title>
		<style>
			body {{ background-color: #111111; font-family: Fira Sans Regular, Arial, sans-serif; color: white; text-align: center; }}
			.channel {{ display: flex; align-items: center; padding: 5px; }}
			.channel img {{ width: 50px; height: auto; margin-right: 10px; }}
			.group-container {{ display: flex; flex-wrap: wrap; justify-content: center; gap: 20px; }}
			.group {{ display: flex; flex-direction: column; margin-top: 20px; font-size: 20px; font-weight: bold; }}
			button {{
				padding: 10px;
				min-width: 200px;
				margin: 5px;
				font-size: 16px;
				color: white;
				border: none;
				transition: background-color 0.2s, transform 0.1s;
				background-color: #222222;
				border-radius: 15px;
			}}
			button.input-btn {{
				padding: 10px;
				min-width: 200px;
				margin: 5px 5px 5px 0;
				font-size: 16px;
				color: white;
				border: none;
				transition: background-color 0.2s, transform 0.1s;
				background-color: #222222;
				border-radius: 0;
				border-top-right-radius: 15px;
				border-bottom-right-radius: 15px;
			}}
			#latency-btn {{
				padding: 10px;
				min-width: 50px;
				margin: 0;
				font-size: 16px;
				color: white;
				border: none;
				transition: background-color 0.2s, transform 0.1s;
				border-radius: 0;
			}}
			input {{
				padding: 10px;
				min-width: 500px;
				margin: 5px 0 5px 5px;
				font-size: 16px;
				color: white;
				border: none;
				transition: background-color 0.2s, transform 0.1s;
				background-color: #303030;
				border-top-left-radius: 15px;
				border-bottom-left-radius: 15px;
			}}
			button:hover {{
				background-color: #444444;
			}}
			button:active {{
				background-color: #666666;
				transform: scale(0.95);
			}}
			button.input-btn:active {{
				background-color: #666666;
				transform: none;
			}}
			button.OFF {{
 				background-color: #770000; /* Default OFF color */
			}}
			button.ON {{
 				background-color: #007700; /* Default OFF color */
			}}
			#osd-on-btn {{
				min-width: 100px;
				margin: 0;
				border-radius: 0;
				border-top-left-radius: 15px;
				border-bottom-left-radius: 15px;
			}}
			#osd-off-btn {{
				min-width: 100px;
				margin: 0;
				border-radius: 0;
				border-top-right-radius: 15px;
				border-bottom-right-radius: 15px;
			}}
		</style>
	</head>
	<body>
		<h1>Welcome to IPMPV</h1>
		<p>Current Channel: {channels[current_index]['name'] if current_index is not None else "None"}</p>
		<button onclick="stopPlayer()">Stop</button>
	"""
#<button onclick="changeChannel({(current_index - 1) % len(channels)})">Previous</button>
#<button onclick="changeChannel({(current_index + 1) % len(channels)})">Next</button>

	global deinterlace
	global low_latency
	deinterlace_state = "ON" if deinterlace else "OFF"
	retroarch_state = "ON" if retroarch_p and retroarch_p.poll() is None else "OFF"
	html += f"""
		<button id="retroarch-btn" class="{retroarch_state}" onclick="toggleRetroArch()"><span id="retroarch-state">{"Stop RetroArch" if retroarch_p and retroarch_p.poll() is None else "Start RetroArch"}</span></button>
		<button id="deinterlace-btn" class="{deinterlace_state}" onclick="toggleDeinterlace()">Deinterlacing: <span id="deinterlace-state">{deinterlace_state}</span></button>
		<button id="resolution-btn" onclick="toggleResolution()">Resolution: <span id="resolution-state">{resolution}</span></button>
		<h2>Toggle OSD</h2>
		<button id="osd-on-btn" onclick="showOSD()">on</button><button id="osd-off-btn" onclick="hideOSD()">off</button>
	"""
	html += f"""
		<h2>Play Custom URL</h2>
		<input type="text" id="custom-url" placeholder="Enter stream URL"><button id="latency-btn" class="{'ON' if low_latency else 'OFF'}" onclick="toggleLatency()"><span id="latency-state">{'Lo' if low_latency else 'Hi'}</span></button><button class="input-btn" onclick="playCustomURL()">Play</button>
		<h2>All Channels</h2>
		<div class="group-container">
	"""

	for group, ch_list in grouped_channels.items():
		html += f'<div class="group">{group}'
		for channel in ch_list:
			index = flat_channel_list.index(channel)  # Get correct global index
			html += f'''
				<div class="channel">
					<img src="{channel['logo']}" onerror="this.style.display='none'">
					<button onclick="changeChannel({index})">{channel['name']}</button>
				</div>
			'''
		html += '</div>'


	html += """
		</div>
		<script>
			function playCustomURL() {
					const url = document.getElementById("custom-url").value;
					if (!url.trim()) return; // Ignore empty input
					fetch(`/play_custom?url=${encodeURIComponent(url)}`)
					.then(response => response.json())
					.then(data => {
					   	if (data.success) {
							alert("Now playing: " + url);
						} else {
			   					alert("Error: " + data.error);
					   	}
					});
			}
			function toggleLatency() {
				fetch(`/toggle_latency`)
				.then(response => response.json())
				.then(data => {
					document.getElementById("latency-state").textContent = data.state ? "Lo" : "Hi";
					document.getElementById("latency-btn").style.backgroundColor = data.state ? "#007700" : "#770000";
				});
			}
			function toggleRetroArch() {
				fetch(`/toggle_retroarch`)
				.then(response => response.json())
				.then(data => {
					document.getElementById("retroarch-state").textContent = data.state ? "Stop RetroArch" : "Start RetroArch";
					document.getElementById("retroarch-btn").style.backgroundColor = data.state ? "#007700" : "#770000";
				});
			}
			function toggleResolution() {
				fetch(`/toggle_resolution`)
				.then(response => response.json())
				.then(data => {
					document.getElementById("resolution-state").textContent = data.res;
				});
			}
			function stopPlayer() {
				fetch(`/stop_player`).then(() => window.location.reload());
			}
			function changeChannel(index) {
				fetch(`/channel?index=${index}`).then(() => window.location.reload());
			}
			function toggleDeinterlace() {
				fetch(`/toggle_deinterlace`)
				.then(response => response.json())
				.then(data => {
					document.getElementById("deinterlace-state").textContent = data.state ? "ON" : "OFF";
					document.getElementById("deinterlace-btn").style.backgroundColor = data.state ? "#007700" : "#770000";
				});
			}
			function showOSD() {
				fetch(`/show_osd`).then(response => response.json())
			}
			function hideOSD() {
				fetch(`/hide_osd`).then(response => response.json())
			}
		</script>
	</body>
	</html>
	"""

	return html

def is_valid_url(url):
	return re.match(r"^(https?|rtmp|rtmps|udp|tcp):\/\/[\w\-]+(\.[\w\-]+)*(:\d+)?([\/?].*)?$", url) is not None

@app.route("/play_custom")
def play_custom():
	global current_index
	current_index = None
	url = request.args.get("url")

	if not url or not is_valid_url(url):
		return jsonify(success=False, error="Invalid or unsupported URL")

	player.loadfile(url)
	return jsonify(success=True)

@app.route("/hide_osd")
def hide_osd():
	to_qt_queue.put({
		'action': 'close_osd',
	})
	return "", 204

@app.route("/show_osd")
def show_osd():
	if current_index is not None:
		channel_info = {
			"name": channels[current_index]["name"],
			"deinterlace": deinterlace,
			"low_latency": low_latency,
			"logo": channels[current_index]["logo"]
		}
		to_qt_queue.put({
			'action': 'show_osd',
			'channel_info': channel_info
		})
		to_qt_queue.put({
			'action': 'update_codecs',
			'vcodec': vcodec,
			'acodec': acodec,
			'video_res': video_res,
			'interlaced': interlaced
		})
	return "", 204

@app.route("/channel")
def switch_channel():
	index = int(request.args.get("index", current_index))
	play_channel(index)
	return "", 204

@app.route("/toggle_deinterlace")
def toggle_deinterlace():
	global deinterlace
	deinterlace = not deinterlace
	if deinterlace:
		player['vf'] = 'yadif=0'
	else:
		player['vf'] = ''
	return jsonify(state=deinterlace)

@app.route("/stop_player")
def stop_player():
	global current_index
	global osd
	current_index = None
	to_qt_queue.put({
		'action': 'close_osd',
	})
	player.stop()
	return "", 204

@app.route("/toggle_retroarch")
def toggle_retroarch():
	global retroarch_p
	retroarch_pid = subprocess.run(["pgrep", "-fx", "retroarch"], stdout=subprocess.PIPE).stdout.strip()
	if retroarch_pid:
		print("Retroarch already open. Trying to close it.")
		subprocess.run(["kill", retroarch_pid])
		retroarch_p.terminate()
		return jsonify(state=False)
	else:
		print("Launching RetroArch")
		retroarch_env = os.environ.copy()
		retroarch_env["MESA_GL_VERSION_OVERRIDE"] = "3.3"
		retroarch_p = subprocess.Popen(re.split('\s', ipmpv_retroarch_cmd if ipmpv_retroarch_cmd is not None else 'retroarch'), env=retroarch_env)
		return jsonify(state=True)

@app.route("/toggle_latency")
def toggle_latency():
	global low_latency
	low_latency = not low_latency
	player['audio-buffer'] = '0' if low_latency else '0.2'
	player['vd-lavc-threads'] = '1' if low_latency else '0'
	player['cache-pause'] = 'no' if low_latency else 'yes'
	player['demuxer-lavf-o'] = 'reconnect=1,fflags=+nobuffer' if low_latency else 'reconnect=1'
	player['demuxer-lavf-probe-info'] = 'nostreams' if low_latency else 'auto'
	player['demuxer-lavf-analyzeduration'] = '0.1' if low_latency else '0'
	player['video-sync'] = 'audio'
	player['interpolation'] = 'no'
	player['video-latency-hacks'] = 'yes' if low_latency else 'no'
	player['stream-buffer-size'] = '4k' if low_latency else '128k'
	print("JSON: ",jsonify(state=low_latency))
	return jsonify(state=low_latency)

@app.route("/toggle_resolution")
def toggle_resolution():
	global resolution,is_wayland
	new_res = ""
	if is_wayland:
		if resolution == "480i":
			new_res = "720x240"
		elif resolution == "240p":
			new_res = "720x480"
		elif resolution == "576i":
			new_res = "720x288"
		elif resolution == "288p":
			new_res = "720x576"

	else:
		if resolution == "480i":
			new_res = "720x240"
		elif resolution == "240p":
			new_res = "720x480i"
		elif resolution == "576i":
			new_res = "720x288"
		elif resolution == "288p":
			new_res = "720x576i"

	if new_res:
		if is_wayland:
			wlr_randr_env = os.environ.copy()
			wlr_randr_env["DISPLAY"] = ":0"
			subprocess.run(["wlr-randr", "--output", "Composite-1", "--mode", new_res], check=False, env=wlr_randr_env)
			resolution = get_current_resolution()
		else:
			xrandr_env = os.environ.copy()
			xrandr_env["DISPLAY"] = ":0"
			subprocess.run(["xrandr", "--output", "Composite-1", "--mode", new_res], check=False, env=xrandr_env)
			resolution = get_current_resolution()

	return jsonify(res=get_current_resolution())

if __name__ == "__main__":
   	# Start Qt process
   	qt_proc = multiprocessing.Process(target=qt_process)
   	qt_proc.daemon = True
   	qt_proc.start()

   	# Start Flask in main thread
   	app.run(host="0.0.0.0", port=5000)
