from pydantic import BaseModel


class LiveWebcast(BaseModel):
    """TikTok 直播 WebSocket 连接参数 (webcast-ws 接口)"""

    # 参数顺序与 TikTok 网页一致
    version_code: str = "270000"
    device_platform: str = "web"
    cookie_enabled: str = "true"
    screen_width: int = 2560
    screen_height: int = 1440
    browser_language: str = "zh-CN"
    browser_platform: str = "Win32"
    browser_name: str = "Mozilla"
    browser_version: str = (
        "5.0%20(Windows%20NT%2010.0;%20Win64;%20x64)%20AppleWebKit/537.36%20(KHTML,%20like%20Gecko)%20Chrome/143.0.0.0%20Safari/537.36%20Edg/143.0.0.0"
    )
    browser_online: str = "true"
    tz_name: str = "Asia/Hong_Kong"
    app_name: str = "tiktok_web"
    sup_ws_ds_opt: int = 1
    update_version_code: str = "2.0.0"
    compress: str = "gzip"
    webcast_language: str = "zh-Hans"
    ws_direct: int = 1
    aid: int = 1988
    live_id: int = 12
    app_language: str = "zh-Hans"
    client_enter: int = 1
    room_id: str  # 房间ID
    identity: str = "audience"
    history_comment_count: int = 6
    last_rtt: int = 0
    heartbeat_duration: int = 10000
    resp_content_type: str = "protobuf"
    did_rule: int = 3
