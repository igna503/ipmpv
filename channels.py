#!/usr/bin/python
"""Channel management for IPMPV."""

import re
import requests
import sys
from utils import m3u_url

def get_channels():
    """
    Get a list of channels from the M3U playlist.
    
    Returns:
        list: A list of channel dictionaries with name, url, logo, and group.
    """
    if m3u_url:
        try:
            response = requests.get(m3u_url)
            response.raise_for_status()  # Raise exception for HTTP errors
        except requests.RequestException as e:
            print(f"Error fetching M3U playlist: {e}")
            return []
    else:
        print("Error: IPMPV_M3U_URL not set. Please set this environment variable to the URL of your IPTV list, in M3U format.")
        sys.exit(1)
        
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

def group_channels(channels):
    """
    Group channels by their group title.
    
    Args:
        channels (list): List of channel dictionaries.
        
    Returns:
        dict: Dictionary of channel groups.
    """
    grouped_channels = {}
    for channel in channels:
        grouped_channels.setdefault(channel["group"], []).append(channel)
    return grouped_channels
