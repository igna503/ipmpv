#!/usr/bin/python
"""Utility functions for IPMPV."""

import os
import re
import subprocess

# Environment variables
is_wayland = "WAYLAND_DISPLAY" in os.environ
osd_corner_radius = os.environ.get("IPMPV_CORNER_RADIUS")
ipmpv_retroarch_cmd = os.environ.get("IPMPV_RETROARCH_CMD")
m3u_url = os.environ.get('IPMPV_M3U_URL')

def setup_environment():
    """Set up environment variables."""
    os.environ["LC_ALL"] = "C"
    os.environ["LANG"] = "C"

def is_valid_url(url):
    """Check if a URL is valid."""
    return re.match(r"^(https?|rtmp|rtmps|udp|tcp):\/\/[\w\-]+(\.[\w\-]+)*(:\d+)?([\/?].*)?$", url) is not None

def get_current_resolution():
    """Get the current display resolution."""
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

def change_resolution(current_resolution):
    """Change the display resolution."""
    new_res = ""
    if is_wayland:
        if current_resolution == "480i":
            new_res = "720x240"
        elif current_resolution == "240p":
            new_res = "720x480"
        elif current_resolution == "576i":
            new_res = "720x288"
        elif current_resolution == "288p":
            new_res = "720x576"
    else:
        if current_resolution == "480i":
            new_res = "720x240"
        elif current_resolution == "240p":
            new_res = "720x480i"
        elif current_resolution == "576i":
            new_res = "720x288"
        elif current_resolution == "288p":
            new_res = "720x576i"

    if new_res:
        if is_wayland:
            wlr_randr_env = os.environ.copy()
            wlr_randr_env["DISPLAY"] = ":0"
            subprocess.run(["wlr-randr", "--output", "Composite-1", "--mode", new_res], check=False, env=wlr_randr_env)
            return get_current_resolution()
        else:
            xrandr_env = os.environ.copy()
            xrandr_env["DISPLAY"] = ":0"
            subprocess.run(["xrandr", "--output", "Composite-1", "--mode", new_res], check=False, env=xrandr_env)
            return get_current_resolution()
            
    return current_resolution
