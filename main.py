import mpv
import requests
import flask
import re
from flask import request

XTEVE_M3U_URL = "http://tv.netpaws.cc/m3u/xteve.m3u"

def get_channels():
    response = requests.get(XTEVE_M3U_URL)
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

player = mpv.MPV(
    vo='gpu',
    demuxer_lavf_o='reconnect=1',
    deinterlace='yes',
    keepaspect = 'no',
    geometry = '100%:100%'
)
channels = get_channels()
current_index = 0

def play_channel(index):
    global current_index
    current_index = index % len(channels)
    print(f"Playing {channels[current_index]["url"]}")
    player.play(channels[current_index]["url"])

play_channel(current_index)

# Flask web server
app = flask.Flask(__name__)

@app.route("/")
def index():
    grouped_channels = {}
    for channel in channels:
        grouped_channels.setdefault(channel["group"], []).append(channel)

    html = f"""
    <html>
    <head>
        <title>IPTV Remote</title>
        <style>
            body {{ background-color: #111111; font-family: Arial, sans-serif; color: white; text-align: center; }}
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
                background-color: #222222;
                border-radius: 15px;
            }}
        </style>
    </head>
    <body>
        <h1>IPTV Remote</h1>
        <p>Current Channel: {channels[current_index]['name']}</p>
        <button onclick="changeChannel({(current_index - 1) % len(channels)})">Previous</button>
        <button onclick="changeChannel({(current_index + 1) % len(channels)})">Next</button>
        <h2>All Channels</h2>
        <div class="group-container">
    """
    
    flat_channel_list = [channel for group in grouped_channels.values() for channel in group]

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
            function changeChannel(index) {
                fetch(`/channel?index=${index}`).then(() => window.location.reload());
            }
        </script>
    </body>
    </html>
    """

    return html

@app.route("/channel")
def switch_channel():
    index = int(request.args.get("index", current_index))
    play_channel(index)
    return "", 204

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)