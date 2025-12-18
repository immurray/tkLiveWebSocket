import asyncio
import json
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from crawler.websocket import DouyinWebSocketCrawler
from log.logger import logger
from model.tiktok import LiveWebcast
from utils.config import Config
from utils.token import fetch_check_live_alive


# 创建 lifespan 上下文管理器
@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时执行，相当于原来的 @app.on_event("startup")
    cleanup_task = asyncio.create_task(check_inactive_rooms())
    yield
    # 关闭时执行，相当于原来的 @app.on_event("shutdown")
    cleanup_task.cancel()
    try:
        await cleanup_task
    except asyncio.CancelledError:
        pass


# 使用 lifespan 参数创建 FastAPI 实例
app = FastAPI(lifespan=lifespan)
room_connections = {}  # room_id: set of WebSocket
room_crawlers = {}  # room_id: DouyinWebSocketCrawler
crawler_tasks = {}  # room_id: asyncio.Task 跟踪爬虫任务
room_last_active = {}  # room_id: last_active_time 记录房间最后活跃时间


@app.get("/")
async def root():
    return {"msg": "Hello, TikHubIO!"}


@app.websocket("/ws/{room_id}")
async def websocket_endpoint(websocket: WebSocket, room_id: str):
    if not room_id:
        logger.error("[WebSocket] [❌ 无效参数] | [房间ID为空]")
        return

    await websocket.accept()

    # 发送连接成功消息
    await websocket.send_text(
        json.dumps(
            {
                "status": "connecting",
                "message": "连接已建立，正在初始化...",
                "step": 1,
                "total_steps": 4,
            }
        )
    )

    room_connections.setdefault(room_id, set()).add(websocket)

    # 检查是否需要创建新爬虫实例
    crawler_exists = room_id in room_crawlers
    crawler_valid = False

    if crawler_exists:
        crawler = room_crawlers[room_id]
        crawler_valid = crawler.websocket is not None and not crawler.websocket.closed

    if not crawler_exists or not crawler_valid:
        # 如果之前的爬虫实例已失效，则删除
        if crawler_exists and not crawler_valid:
            logger.info(
                f"[WebSocket] [🔄 重置爬虫] | [房间ID: {room_id}] [之前的连接已关闭]"
            )
            del room_crawlers[room_id]

        # 发送爬虫创建消息
        await websocket.send_text(
            json.dumps(
                {
                    "status": "creating_crawler",
                    "message": "正在创建直播爬虫实例...",
                    "step": 2,
                    "total_steps": 4,
                }
            )
        )

        # 创建新的爬虫实例
        async def broadcast_callback(data):
            if not data:
                return

            clients = list(room_connections.get(room_id, []))
            if not clients:
                return

            # 创建一个需要移除的连接列表，避免在遍历过程中修改集合
            disconnected_clients = []

            for ws in clients:
                try:
                    # 更严格地检查WebSocket状态
                    if ws.client_state.name != "CONNECTED" or getattr(
                        ws, "_closed", False
                    ):
                        disconnected_clients.append(ws)
                        continue

                    # 使用尝试发送，如果失败则捕获特定异常
                    await ws.send_text(data if isinstance(data, str) else str(data))
                except RuntimeError as e:
                    if "already completed" in str(e) or "was closed" in str(e):
                        logger.warning(f"[Broadcast] [❗ 连接已关闭] | [无法发送消息]")
                        disconnected_clients.append(ws)
                    else:
                        logger.error(f"[Broadcast] [⚠️ 发送消息失败] | [错误: {str(e)}]")
                        disconnected_clients.append(ws)
                except Exception as e:
                    logger.error(f"[Broadcast] [⚠️ 发送消息失败] | [错误: {str(e)}]")
                    disconnected_clients.append(ws)

            # 批量移除断开的连接
            for ws in disconnected_clients:
                if room_id in room_connections and ws in room_connections[room_id]:
                    room_connections[room_id].discard(ws)

        # 获取必要参数，检查空值
        await websocket.send_text(
            json.dumps(
                {
                    "status": "getting_token",
                    "message": "正在获取访问令牌...",
                    "step": 3,
                    "total_steps": 4,
                }
            )
        )

        kwargs = {
            "headers": {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36 Edg/143.0.0.0",
                "Origin": "https://www.tiktok.com",
                "Cache-Control": "no-cache",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6",
                "Pragma": "no-cache",
            },
            "proxies": {"http://": None, "https://": None},
            "timeout": 60,
            "cookie": Config.WSS_COOKIES,
        }

        # 创建爬虫实例
        crawler = DouyinWebSocketCrawler(kwargs=kwargs)

        # 设置消息类型回调字典
        wss_callbacks = {
            "WebcastChatMessage": crawler.WebcastChatMessage,
            # 最后添加广播回调
            "broadcast": broadcast_callback,
        }

        # 更新爬虫的回调
        crawler.callbacks = wss_callbacks
        crawler.broadcast_callback = broadcast_callback

        room_crawlers[room_id] = crawler

        # 检查直播状态
        await websocket.send_text(
            json.dumps(
                {
                    "status": "checking_live",
                    "message": "正在检查直播状态...",
                    "step": 4,
                    "total_steps": 4,
                }
            )
        )

        check_live_alive = await fetch_check_live_alive(room_id=room_id)

        if not check_live_alive:
            logger.error(f"[WebSocket] [❌ 检查直播状态失败] | [房间ID: {room_id}]")
            await websocket.send_text(
                json.dumps(
                    {
                        "error": "无法检查直播状态",
                        "detail": "请确认房间ID正确且主播正在直播中",
                    }
                )
            )
            # 主动断开连接
            await websocket.close()
            return

        # 安全地检查直播状态
        live_data = check_live_alive.get("live_room_status", {}).get("data", [])

        if not live_data or not live_data[0].get("alive", False):
            logger.error(f"[WebSocket] [❌ 房间不在直播状态] | [房间ID: {room_id}]")
            await websocket.send_text(
                json.dumps(
                    {
                        "error": "房间不在直播状态",
                        "detail": "请确认房间ID正确且主播正在直播中",
                    }
                )
            )
            # 主动断开连接
            await websocket.close()
            return

        # 构建WebSocket连接参数 (webcast-ws 接口)
        params = LiveWebcast(room_id=room_id)

        # 发送连接成功消息
        await websocket.send_text(
            json.dumps(
                {
                    "status": "connected",
                    "message": "🎉 连接成功！等待接收直播弹幕消息...",
                    "step": 4,
                    "total_steps": 4,
                }
            )
        )

        # 在参数设置后，创建并跟踪爬虫任务
        async def run_crawler():
            max_crawler_retries = 3
            crawler_retry_count = 0

            while crawler_retry_count < max_crawler_retries:
                try:
                    await crawler.fetch_live_danmaku(params)
                    break  # 如果成功运行，跳出重试循环

                except ConnectionError as e:
                    crawler_retry_count += 1

                    if "网络问题" in str(e) or "ConnectionResetError" in str(e):
                        logger.warning(
                            f"[WebSocket] [🔄 网络连接问题，爬虫重试] | "
                            f"[房间ID: {room_id}] | [重试次数: {crawler_retry_count}/{max_crawler_retries}] | "
                            f"[错误: {str(e)}]"
                        )

                        if crawler_retry_count < max_crawler_retries:
                            # 等待后重试
                            await asyncio.sleep(5 * crawler_retry_count)
                            continue

                    # 达到最大重试次数或其他连接错误
                    logger.error(
                        f"[WebSocket] [❌ 爬虫连接失败] | [房间ID: {room_id}] | [错误: {str(e)}]"
                    )

                    # 只向仍然连接的客户端发送错误消息
                    if room_id in room_connections and room_connections[room_id]:
                        if "网络问题" in str(e) or "ConnectionResetError" in str(e):
                            error_message = json.dumps(
                                {
                                    "error": "网络连接不稳定",
                                    "detail": "无法连接到TikTok服务器，请检查网络连接或稍后重试",
                                    "suggestion": "建议使用更稳定的网络环境或考虑使用代理",
                                    "reconnect": True,
                                }
                            )
                        else:
                            error_message = json.dumps(
                                {
                                    "error": "直播连接失败",
                                    "detail": f"连接错误: {str(e)[:200]}",
                                    "reconnect": True,
                                }
                            )
                        await broadcast_callback(error_message)
                    break

                except Exception as e:
                    crawler_retry_count += 1
                    logger.error(
                        f"[WebSocket] [❌ 爬虫任务异常] | [房间ID: {room_id}] | "
                        f"[重试次数: {crawler_retry_count}/{max_crawler_retries}] | [错误: {str(e)}]"
                    )

                    if crawler_retry_count >= max_crawler_retries:
                        # 只向仍然连接的客户端发送错误消息
                        if room_id in room_connections and room_connections[room_id]:
                            error_message = json.dumps(
                                {
                                    "error": "直播连接异常",
                                    "detail": f"连接中断: {str(e)[:200]}",
                                    "reconnect": True,
                                }
                            )
                            await broadcast_callback(error_message)
                        break

                    await asyncio.sleep(3 * crawler_retry_count)

            # 清理爬虫实例
            if room_id in room_crawlers:
                await room_crawlers[room_id].close()
                del room_crawlers[room_id]
            if room_id in crawler_tasks:
                del crawler_tasks[room_id]
            if room_id in room_last_active:
                del room_last_active[room_id]

        danmaku_task = asyncio.create_task(run_crawler())
        crawler_tasks[room_id] = danmaku_task
        room_last_active[room_id] = asyncio.get_event_loop().time()
    else:
        # 如果爬虫已存在，直接发送连接成功消息
        await websocket.send_text(
            json.dumps(
                {
                    "status": "connected",
                    "message": "🎉 连接成功！直播爬虫已在运行中...",
                    "step": 4,
                    "total_steps": 4,
                }
            )
        )

    # 定义清理函数
    async def cleanup_resources():
        """清理房间资源"""
        try:
            if room_id in room_connections and websocket in room_connections[room_id]:
                room_connections[room_id].remove(websocket)
                logger.info(f"[WebSocket] [🔌 移除客户端连接] | [房间ID: {room_id}]")

                # 检查房间是否还有其他连接，如果没有，清理爬虫实例
                if not room_connections[room_id]:
                    if room_id in room_crawlers:
                        logger.info(
                            f"[WebSocket] [🧹 清理资源] | [房间ID: {room_id}] [爬虫实例已移除]"
                        )

                        crawler = room_crawlers[room_id]
                        await crawler.close()  # 主动关闭WebSocket连接

                        # 取消任务
                        if room_id in crawler_tasks:
                            task = crawler_tasks[room_id]
                            if not task.done() and not task.cancelled():
                                task.cancel()
                                try:
                                    await task
                                except asyncio.CancelledError:
                                    pass
                            del crawler_tasks[room_id]

                        del room_crawlers[room_id]
                        if room_id in room_last_active:
                            del room_last_active[room_id]
        except Exception as e:
            logger.error(f"[WebSocket] [⚠️ 清理资源时发生错误] | [错误: {str(e)}]")

    try:
        while True:
            # 接收客户端消息
            message = await websocket.receive_text()

            try:
                # 尝试解析JSON消息
                data = json.loads(message)

                # 检查是否是关闭消息
                if data.get("action") == "close" or data.get("type") == "close":
                    logger.info(
                        f"[WebSocket] [📤 收到客户端关闭请求] | [房间ID: {room_id}]"
                    )

                    # 发送确认关闭消息
                    try:
                        await websocket.send_text(
                            json.dumps(
                                {
                                    "status": "closing",
                                    "message": "正在关闭连接...",
                                }
                            )
                        )
                    except RuntimeError:
                        # 如果连接已经关闭，忽略发送错误
                        pass

                    # 执行清理
                    await cleanup_resources()

                    # 主动关闭连接
                    try:
                        await websocket.close()
                    except RuntimeError:
                        # 连接可能已经关闭
                        pass
                    break

                # 处理其他类型的消息
                elif data.get("type") == "ping":
                    # 处理心跳消息
                    try:
                        await websocket.send_text(
                            json.dumps(
                                {
                                    "type": "pong",
                                    "timestamp": int(time.time() * 1000),  # 毫秒时间戳
                                }
                            )
                        )
                    except RuntimeError:
                        # 连接已关闭
                        break

            except json.JSONDecodeError:
                # 如果不是JSON格式，记录并继续
                logger.warning(
                    f"[WebSocket] [⚠️ 收到非JSON消息] | [房间ID: {room_id}] | [消息: {message}]"
                )

    except WebSocketDisconnect:
        logger.info(f"[WebSocket] [🔌 客户端主动断开连接] | [房间ID: {room_id}]")
        await cleanup_resources()

    except Exception as e:
        logger.error(
            f"[WebSocket] [⚠️ 连接异常] | [房间ID: {room_id}] | [错误: {str(e)}]"
        )
        await cleanup_resources()


# 定期检查并关闭无活跃连接的爬虫实例
async def check_inactive_rooms():
    """定期检查并关闭无活跃连接的房间爬虫"""
    INACTIVE_TIMEOUT = 300  # 5分钟无活跃连接则关闭
    CHECK_INTERVAL = 60  # 每分钟检查一次

    while True:
        await asyncio.sleep(CHECK_INTERVAL)
        current_time = asyncio.get_event_loop().time()
        rooms_to_close = []

        # 找出需要关闭的房间
        for room_id, last_active in room_last_active.items():
            if current_time - last_active > INACTIVE_TIMEOUT:
                if room_id not in room_connections or not room_connections[room_id]:
                    rooms_to_close.append(room_id)

        # 关闭并清理资源
        for room_id in rooms_to_close:
            if room_id in room_crawlers:
                logger.info(
                    f"[AutoCleanup] [🧹 清理超时资源] | [房间ID: {room_id}] [无活跃连接超过5分钟]"
                )
                crawler = room_crawlers[room_id]
                await crawler.close()  # 主动关闭WebSocket连接

                # 取消任务
                if room_id in crawler_tasks:
                    task = crawler_tasks[room_id]
                    if not task.done() and not task.cancelled():
                        task.cancel()
                        try:
                            await task
                        except asyncio.CancelledError:
                            pass
                    del crawler_tasks[room_id]

                del room_crawlers[room_id]
                if room_id in room_last_active:
                    del room_last_active[room_id]
