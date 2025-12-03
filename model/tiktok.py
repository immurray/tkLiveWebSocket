from urllib.parse import quote

from pydantic import BaseModel


class BaseWebCastModel(BaseModel):
    aid: str = "1988"
    app_language: str = "zh-Hans"
    app_name: str = "tiktok_web"
    browser_language: str = "zh-CN"
    browser_name: str = "Mozilla"
    browser_online: str = "true"
    browser_platform: str = "Win32"
    browser_version: str = quote(
        "5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36 Edg/130.0.0.0",
        safe="",
    )
    cookie_enabled: str = "true"
    debug: str = "false"
    device_platform: str = "web"
    host: str = quote("https://webcast.tiktok.com", safe="")
    identity: str = "audience"
    live_id: int = 12
    screen_height: int = 1080
    screen_width: int = 1920
    sup_ws_ds_opt: int = 1
    tz_name: str = quote("Asia/Hong_Kong", safe="")
    version_code: str = "270000"


class LiveWebcast(BaseWebCastModel):
    compress: str = "gzip"
    heartbeatDuration: int = 0
    imprp: str = ""
    room_id: str
    cursor: str
    internal_ext: str
    update_version_code: str = "1.3.0"
    webcast_sdk_version: str = "1.3.0"
    wrss: str
