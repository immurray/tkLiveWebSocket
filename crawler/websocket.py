import asyncio
import gzip
import json
import time
import traceback
from datetime import datetime
from typing import Any, Optional, Type, Union

import httpx
import websockets
import websockets_proxy  # type: ignore[import-untyped]
from google.protobuf import json_format
from google.protobuf.message import DecodeError as ProtoDecodeError
from websockets import (
    ConnectionClosedError,
    ConnectionClosedOK,
    WebSocketServerProtocol,
    serve,
)
from websockets.client import WebSocketClientProtocol

from log.logger import logger
from model.tiktok import LiveWebcast
from proto.tiktok.tiktok_webcast_pb2 import (
    PushFrame,
    Response,
    GiftMessage,
    ChatMessage,
    MemberMessage,
    SocialMessage,
    LinkMicFanTicketMethod,
)
from utils.endpoint import BaseEndpointManager


class DouyinWebSocketCrawler:

    def __init__(self, kwargs: Optional[dict] = None, callbacks: Optional[dict] = None):
        # 需要与cli同步
        kwargs = kwargs or {}
        self.headers = kwargs.get("headers", {}) | {"Cookie": kwargs.get("cookie", {})}
        self.callbacks = callbacks or {}
        # 保留原始的broadcast回调，同时保留其他消息类型回调
        self.broadcast_callback = self.callbacks.get("broadcast", None)
        self.timeout = kwargs.get("timeout", 20)  # 超时时间
        self.connected_clients: set[WebSocketServerProtocol] = set()  # 管理连接的客户端
        self.websocket: Optional[WebSocketClientProtocol] = None
        self.wss_headers = self.headers
        proxy = kwargs.get("proxies", {"http://": None, "https://": None}).get(
            "http://"
        )
        self.proxy = websockets_proxy.Proxy.from_url(proxy) if proxy else None

    async def connect_websocket(
        self,
        websocket_uri: str,
    ):
        """
        连接 WebSocket

        Args:
            websocket_uri: WebSocket URI (ws:// or wss://)
        """
        max_retries = 5
        retry_count = 0
        base_delay = 2

        while retry_count < max_retries:
            try:
                # 设置更长的连接超时时间
                connect_timeout = 30 + (retry_count * 10)  # 递增超时时间

                if self.proxy:
                    self.websocket = await asyncio.wait_for(
                        websockets_proxy.proxy_connect(
                            websocket_uri,
                            extra_headers=self.wss_headers,
                            proxy=self.proxy,
                            ping_interval=None,
                            ping_timeout=30,
                        ),
                        timeout=connect_timeout,
                    )
                else:
                    self.websocket = await asyncio.wait_for(
                        websockets.connect(
                            websocket_uri,
                            extra_headers=self.wss_headers,
                            ping_interval=None,
                            ping_timeout=30,
                        ),
                        timeout=connect_timeout,
                    )

                logger.info(
                    "[ConnectWebsocket] [🌐 已连接 WebSocket] | [服务器：{0}] | [重试次数: {1}]".format(
                        websocket_uri, retry_count
                    )
                )
                return  # 连接成功，退出重试循环

            except (ConnectionResetError, ConnectionRefusedError, OSError) as exc:
                retry_count += 1
                # 使用指数退避算法计算延迟时间
                delay = base_delay * (2**retry_count) + (retry_count * 2)

                logger.warning(
                    f"[ConnectWebSocket] [🔄 网络连接问题，准备重试] | "
                    f"[尝试次数: {retry_count}/{max_retries}] | "
                    f"[延迟: {delay}秒] | [错误：{type(exc).__name__}: {str(exc)}]"
                )

                if retry_count >= max_retries:
                    logger.error(
                        f"[ConnectWebSocket] [❌ 连接失败，已达最大重试次数] | "
                        f"[最终错误：{type(exc).__name__}: {str(exc)}]"
                    )
                    raise ConnectionError(
                        f"[ConnectWebSocket] [❌ WebSocket 连接失败] | "
                        f"[网络问题，重试{max_retries}次后仍失败] | [错误：{str(exc)}]"
                    )

                # 等待后重试
                await asyncio.sleep(delay)

            except asyncio.TimeoutError as exc:
                retry_count += 1
                delay = base_delay * retry_count

                logger.warning(
                    f"[ConnectWebSocket] [⏰ 连接超时，准备重试] | "
                    f"[尝试次数: {retry_count}/{max_retries}] | [延迟: {delay}秒]"
                )

                if retry_count >= max_retries:
                    logger.error(f"[ConnectWebSocket] [❌ 连接超时，已达最大重试次数]")
                    raise ConnectionError(
                        f"[ConnectWebSocket] [❌ WebSocket 连接失败] | "
                        f"[连接超时，重试{max_retries}次后仍失败]"
                    )

                await asyncio.sleep(delay)

            except websockets.InvalidStatusCode as exc:
                retry_count += 1
                delay = base_delay * retry_count

                logger.warning(
                    f"[ConnectWebSocket] [⚠️ 无效状态码，准备重试] | "
                    f"[尝试次数: {retry_count}/{max_retries}] | "
                    f"[状态码：{exc.status_code}] | [延迟: {delay}秒]"
                )

                if retry_count >= max_retries:
                    logger.error(
                        f"[ConnectWebSocket] [❌ 状态码错误，已达最大重试次数] | [状态码：{exc.status_code}]"
                    )
                    raise ConnectionError(
                        f"[ConnectWebSocket] [❌ WebSocket 连接失败] | "
                        f"[状态码错误：{exc.status_code}]"
                    )

                await asyncio.sleep(delay)

            except Exception as exc:
                retry_count += 1
                delay = base_delay * retry_count

                logger.warning(
                    f"[ConnectWebSocket] [⚠️ 未知错误，准备重试] | "
                    f"[尝试次数: {retry_count}/{max_retries}] | "
                    f"[错误类型：{type(exc).__name__}] | [延迟: {delay}秒]"
                )

                if retry_count >= max_retries:
                    logger.error(traceback.format_exc())
                    logger.error(
                        f"[ConnectWebSocket] [❌ 连接失败，已达最大重试次数] | [错误：{str(exc)}]"
                    )
                    raise ConnectionError(
                        f"[ConnectWebSocket] [❌ WebSocket 连接失败] | [错误：{str(exc)}]"
                    )

                await asyncio.sleep(delay)

    async def receive_messages(self):
        """
        接收 WebSocket 消息并处理
        """

        logger.info("[ReceiveMessages] [📩 开始接收消息]")
        logger.info("[ReceiveMessages] [⏱ 消息等待超时：{0} 秒]".format(self.timeout))

        timeout_count = 0

        while True:
            try:
                if self.websocket is None:
                    logger.error("[ReceiveMessages] [❌ WebSocket未连接]")
                    return "closed"

                message = await asyncio.wait_for(
                    self.websocket.recv(), timeout=self.timeout
                )
                # 为wss连接设置10秒超时机制
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                logger.info("[ReceiveMessages] | [⏳ 接收消息 {0}]".format(timestamp))

                timeout_count = 0  # 重置超时计数
                await self.on_message(message)

            except asyncio.TimeoutError:
                timeout_count += 1
                logger.warning(
                    "[ReceiveMessages] [⚠️ 超时] | [超时次数：{0} / 3]".format(
                        timeout_count
                    )
                )
                if timeout_count >= 3:
                    logger.warning(
                        "[ReceiveMessages] [❌ 超时关闭连接] | "
                        "[超时次数：{0}] [连接状态：未连接]".format(timeout_count)
                    )
                    await self.close()  # 主动关闭连接
                    return "closed"
                if self.websocket is None or self.websocket.closed:
                    logger.warning(
                        "[ReceiveMessages] [🔒 远程服务器关闭] | [WebSocket 连接结束]"
                    )
                    await self.close()  # 确保连接被关闭
                    return "closed"
            except ConnectionClosedError as exc:
                # 区分正常关闭和异常关闭
                if "sent 1000 (OK)" in str(exc):
                    logger.info("[ReceiveMessages] [✓ 连接已正常关闭]")
                elif "keepalive ping timeout" in str(exc):
                    logger.warning(
                        f"[ReceiveMessages] [💔 Ping超时断开] | [原因：{exc}]"
                    )
                elif "internal error" in str(exc):
                    logger.warning(
                        f"[ReceiveMessages] [⚠️ 内部错误断开] | [原因：{exc}]"
                    )
                else:
                    logger.warning(f"[ReceiveMessages] [🔌 连接关闭] | [原因：{exc}]")
                await self.close()  # 确保连接被关闭
                return "closed"

            except ConnectionClosedOK:
                logger.info("[ReceiveMessages] [✔️ 正常关闭] | [WebSocket 连接正常关闭]")
                await self.close()  # 确保连接被关闭
                return "closed"

            except Exception as exc:
                logger.error(traceback.format_exc())
                logger.error(
                    "[ReceiveMessages] [⚠️ 消息处理错误] | [错误：{0}]".format(exc)
                )
                await self.close()  # 发生异常时关闭连接
                return "error"

    async def fetch_live_danmaku(self, params: LiveWebcast) -> None:
        endpoint = BaseEndpointManager.model_2_endpoint(
            "wss://webcast16-ws-alisg.tiktok.com/webcast/im/ws_proxy/ws_reuse_supplement/",
            params.model_dump(),
        )
        logger.info(
            "[FetchLiveDanmaku] [🔗 直播弹幕接口地址] | [地址：{0}]".format(endpoint)
        )

        await self.connect_websocket(endpoint)
        await self.receive_messages()  # 只需要这两步

    async def handle_wss_message(self, message: bytes) -> None:
        """处理 WebSocket 消息"""
        try:
            wss_package = PushFrame()
            wss_package.ParseFromString(message)

            logger.debug("[WssPackage] [📦Wss包] | [{0}]".format(wss_package))

            try:
                decompressed = gzip.decompress(wss_package.payload)
            except gzip.BadGzipFile:
                decompressed = wss_package.payload

            payload_package = Response()
            payload_package.ParseFromString(decompressed)

            logger.debug(
                "[PayloadPackage] [📦Payload包] | [{0}]".format(payload_package)
            )

            # 发送 ack 包
            if payload_package.needAck:
                await self.send_ack(wss_package.logid, payload_package.internalExt)

            # 消息处理任务
            tasks = []
            for msg in payload_package.messages:
                method = msg.method
                payload = msg.payload

                # 添加调试日志
                logger.debug(f"[HandleWssMessage] [📩收到消息类型] | [方法：{method}]")

                # 消息处理管道
                processed_data = await self.process_message(method, payload)

                # 如果有消息需要广播且存在广播回调
                if processed_data is not None and self.broadcast_callback:
                    # 检查是否还有活跃连接，如果没有则跳过广播
                    tasks.append(self.broadcast_callback(processed_data))

            # 并发运行所有广播任务
            if tasks:
                results = await asyncio.gather(*tasks, return_exceptions=True)

                # 处理错误
                for result in results:
                    if isinstance(result, Exception):
                        logger.error(
                            "[HandleWssMessage] [⚠️ 广播执行出错] | [错误：{0}]".format(
                                result
                            )
                        )

            # 增加保活机制
            # await self.send_ack(wss_package.LogID, payload_package.internal_ext)

        except Exception:
            logger.error(traceback.format_exc())

    async def process_message(self, method: str, payload: bytes) -> Optional[str]:
        """
        处理各种类型的消息
        """
        if not method or not payload:
            logger.warning("[ProcessMessage] [⚠️ 无效参数] | [方法或数据为空]")
            return None

        try:
            # 首先检查callbacks中是否有对应的处理函数
            if method in self.callbacks and callable(self.callbacks[method]):
                # 通过回调字典调用对应的方法
                result = await self.callbacks[method](payload)
                return result
            # 然后尝试调用对应类型的类方法
            method_handler = getattr(self, method, None) if method else None
            if method_handler and callable(method_handler):
                # 如果存在对应方法，则调用
                result = await method_handler(payload)
                return result
            else:
                pass
            return None
        except Exception as e:
            logger.error(
                f"[ProcessMessage] [⚠️ 处理消息出错] | [方法: {method}] | [错误: {str(e)}]"
            )
            return None

    async def send_ack(self, log_id: int, internal_ext: str) -> None:
        """发送 ack 包"""
        if self.websocket is None or self.websocket.closed:
            logger.warning(
                "[SendAck] [❌ 无法发送 ack 包] | [WebSocket 未连接或已关闭]"
            )
            return

        if log_id is None or internal_ext is None:
            logger.warning("[SendAck] [❌ 无效参数] | [日志ID或扩展为空]")
            return

        try:
            ack = PushFrame()
            ack.logid = log_id
            ack.payload_type = internal_ext
            data = ack.SerializeToString()
            logger.info(f"[SendAck] [💓 发送 ack 包] | [日志ID: {log_id}]")

            await self.websocket.send(data)
        except Exception as e:
            logger.error(f"[SendAck] [⚠️ 发送失败] | [错误: {str(e)}]")

    async def send_ping(self) -> None:
        """发送 ping 包"""
        if self.websocket is None:
            logger.warning("[SendPing] [❌ 无法发送 ping 包] | [WebSocket 未连接]")
            return

        ping = PushFrame()
        ping.payload_type = "hb"
        data = ping.SerializeToString()
        logger.info("[SendPing] [📤 发送 ping 包]")
        await self.websocket.ping(data)

    async def on_message(self, message):
        await self.handle_wss_message(message)

    async def on_error(self, message):
        return await super().on_error(message)

    async def on_close(self, message):
        return await super().on_close(message)

    async def on_open(self):
        return await super().on_open()

    @classmethod
    async def WebcastGiftMessage(cls, data: bytes) -> dict:
        """处理直播间礼物消息"""
        if not data:
            logger.warning("[WebcastGiftMessage] [⚠️ 空数据] | [无消息内容]")
            return json.dumps({"error": "Empty message data"})
        try:
            giftMessage = GiftMessage()
            giftMessage.ParseFromString(data)
            data_json = json.loads(
                json_format.MessageToJson(
                    giftMessage,
                    preserving_proto_field_name=True,
                    ensure_ascii=False,
                )
            )
            nick_name = data_json.get("user").get("nickname", "N/A")
            gift_name = data_json.get("gift").get("describe", "N/A")
            gift_price = data_json.get("gift").get("diamondCount", "N/A")

            logger.info(
                f"[WebcastGiftMessage] [🎁直播间礼物] [用户：{nick_name} 送出了 {gift_name} 价值 {gift_price} 钻石]"
            )
            return json.dumps(data_json)
        except Exception as e:
            logger.error(f"[WebcastGiftMessage] [⚠️ 解析失败] | [错误: {str(e)}]")
            return json.dumps({"error": "Failed to parse message", "details": str(e)})

    @classmethod
    async def WebcastChatMessage(cls, data: bytes) -> dict:
        """
        处理直播间消息

        Args:
            data (bytes): 直播间消息的字节数据

        Returns:
            dict: 直播间消息的 JSON 数据
        """
        if not data:
            logger.warning("[WebcastChatMessage] [⚠️ 空数据] | [无消息内容]")
            return json.dumps({"error": "Empty message data"})
        try:
            chatMessage = ChatMessage()
            chatMessage.ParseFromString(data)
            data_json = json.loads(
                json_format.MessageToJson(
                    chatMessage,
                    preserving_proto_field_name=True,
                    ensure_ascii=False,
                )
            )

            nick_name = data_json.get("user").get("nickname")
            content = data_json.get("content")

            logger.info(
                f"[WebcastChatMessage] [💬直播间消息] [用户：{nick_name} 说：{content}]"
            )
            return json.dumps(data_json)
        except Exception as e:
            logger.error(f"[WebcastChatMessage] [⚠️ 解析失败] | [错误: {str(e)}]")
            return json.dumps({"error": "Failed to parse message", "details": str(e)})

    @classmethod
    async def WebcastMemberMessage(cls, data: bytes) -> dict:
        """
        处理直播间成员消息

        Args:
            data (bytes): 直播间成员消息的字节数据

        Returns:
            dict: 直播间成员消息的 JSON 数据
        """
        if not data:
            logger.warning("[WebcastMemberMessage] [⚠️ 空数据] | [无消息内容]")
            return json.dumps({"error": "Empty message data"})
        try:
            memberMessage = MemberMessage()
            memberMessage.ParseFromString(data)
            data_json = json.loads(
                json_format.MessageToJson(
                    memberMessage,
                    preserving_proto_field_name=True,
                    ensure_ascii=False,
                )
            )

            nick_name = data_json.get("user").get("nickname")

            logger.info(
                f"[WebcastMemberMessage] [👥直播间成员消息] [用户：{nick_name} 加入了直播间]"
            )
            return json.dumps(data_json)
        except Exception as e:
            logger.error(f"[WebcastMemberMessage] [⚠️ 解析失败] | [错误: {str(e)}]")
            return json.dumps({"error": "Failed to parse message", "details": str(e)})

    @classmethod
    async def WebcastSocialMessage(cls, data: bytes) -> dict:
        """
        处理直播间社交消息

        Args:
            data (bytes): 直播间社交消息的字节数据

        Returns:
            dict: 直播间社交消息的 JSON 数据
        """
        if not data:
            logger.warning("[WebcastSocialMessage] [⚠️ 空数据] | [无消息内容]")
            return json.dumps({"error": "Empty message data"})
        try:
            socialMessage = SocialMessage()
            socialMessage.ParseFromString(data)
            data_json = json.loads(
                json_format.MessageToJson(
                    socialMessage,
                    preserving_proto_field_name=True,
                    ensure_ascii=False,
                )
            )
            nick_name = data_json.get("user").get("nickname")

            logger.info(
                f"[WebcastSocialMessage] [➕观众关注] [用户：{nick_name} 关注了主播]"
            )
            return json.dumps(data_json)
        except Exception as e:
            logger.error(f"[WebcastSocialMessage] [⚠️ 解析失败] | [错误: {str(e)}]")
            return json.dumps({"error": "Failed to parse message", "details": str(e)})

    @classmethod
    async def WebcastLinkMicFanTicketMethod(cls, data: bytes) -> dict:
        """
        处理直播间连麦粉丝票消息

        Args:
            data (bytes): 直播间连麦粉丝票消息的字节数据

        Returns:
            dict: 直播间连麦粉丝票消息的 JSON 数据
        """
        if not data:
            logger.warning("[WebcastLinkMicFanTicketMethod] [⚠️ 空数据] | [无消息内容]")
            return json.dumps({"error": "Empty message data"})
        try:
            linkMicFanTicketMethod = LinkMicFanTicketMethod()
            linkMicFanTicketMethod.ParseFromString(data)
            data_json = json.loads(
                json_format.MessageToJson(
                    linkMicFanTicketMethod,
                    preserving_proto_field_name=True,
                    ensure_ascii=False,
                )
            )

            logger.info(f"[WebcastLinkMicFanTicketMethod] [🎟️连麦粉丝票] {data_json}")
            return json.dumps(data_json)
        except Exception as e:
            logger.error(
                f"[WebcastLinkMicFanTicketMethod] [⚠️ 解析失败] | [错误: {str(e)}]"
            )
            return json.dumps({"error": "Failed to parse message", "details": str(e)})

    async def close(self):
        """主动关闭WebSocket连接"""
        if self.websocket is not None:
            try:
                if not self.websocket.closed:
                    logger.info("[CloseWebSocket] [🔌 主动关闭连接]")
                    # 设置一个短超时时间强制关闭
                    await asyncio.wait_for(self.websocket.close(), timeout=2.0)
                else:
                    logger.info("[CloseWebSocket] [✓ 连接已处于关闭状态]")
            except (asyncio.TimeoutError, Exception) as e:
                logger.warning(f"[CloseWebSocket] [⚠️ 强制关闭连接] | [错误: {str(e)}]")
            finally:
                self.websocket = None
                logger.info("[CloseWebSocket] [✅ 连接资源已清理]")

    async def __aenter__(self):
        await super().__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await super().__aexit__(exc_type, exc_val, exc_tb)
