"""Local camera settings. No credentials or household addresses are shipped."""
from dataclasses import dataclass
import ipaddress
import json
import os
from pathlib import Path
import re

@dataclass(frozen=True)
class CameraConfig:
    camera_host: str = ''
    blink_host: str = ''
    home_assistant_host: str = ''
    home_assistant_port: int = 8123
    viewer_helper: Path = Path.home() / '.local/bin/foxtail-reolink-view'


def clean_host(value):
    if not isinstance(value, str):
        raise ValueError('Device hosts must be strings.')
    if not value:
        return ''
    # IPv4 and DNS names only: no URL credentials, ports, or command options.
    try:
        address = ipaddress.IPv4Address(value)
        return str(address)
    except ipaddress.AddressValueError:
        pass
    if len(value) > 253 or not re.fullmatch(r'[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?', value):
        raise ValueError('Use an IPv4 address or DNS hostname for a device.')
    if any(not label or len(label)>63 or label.startswith('-') or label.endswith('-') for label in value.split('.')):
        raise ValueError('Use a valid DNS hostname for a device.')
    if re.fullmatch(r'[0-9.]+',value):
        raise ValueError('Use a valid IPv4 address for a device.')
    return value


def load_config(path=None):
    config_path = Path(path or os.environ.get('FOXTAIL_CAMERAS_CONFIG', Path.home()/'.config/foxtail-cameras/config.json')).expanduser()
    if not config_path.exists():
        return CameraConfig()
    try:
        data = json.loads(config_path.read_text())
    except (OSError, ValueError):
        raise ValueError('Could not read the private camera configuration.') from None
    fields = set(CameraConfig.__dataclass_fields__)
    if not isinstance(data, dict) or set(data)-fields:
        raise ValueError('Camera configuration contains unknown fields.')
    port = data.get('home_assistant_port',8123)
    if type(port) is not int or not 1 <= port <= 65535:
        raise ValueError('Home Assistant port must be between 1 and 65535.')
    helper_value = data.get('viewer_helper',str(CameraConfig.viewer_helper))
    if not isinstance(helper_value,str) or not helper_value:
        raise ValueError('Viewer helper must be a local file path.')
    helper = Path(helper_value).expanduser()
    if not helper.is_absolute():
        raise ValueError('Viewer helper must be an absolute local file path.')
    return CameraConfig(**{key:clean_host(data.get(key,'')) for key in ('camera_host','blink_host','home_assistant_host')},home_assistant_port=port,viewer_helper=helper)
