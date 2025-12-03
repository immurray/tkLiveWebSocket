## README.md 文档

# TikHub WebCast Live

TikHub WebCast Live 是一个高性能的TikTok直播弹幕和互动消息采集与转发服务。该服务建立与TikTok直播的WebSocket连接，实时获取直播间的聊天消息、点赞、礼物等互动数据，并通过WebSocket接口提供给客户端使用。

## 功能特点

- 实时采集TikTok直播间弹幕和互动消息
- 支持多房间同时监听
- WebSocket消息转发，便于前端实时展示
- 可扩展的消息处理回调机制
- 自动维护WebSocket连接和重连
- 支持通过代理服务器连接

## 技术架构

- **后端框架**：FastAPI
- **WebSocket**：websockets
- **消息解析**：Protocol Buffers (protobuf)
- **HTTP客户端**：httpx
- **日志系统**：自定义logger

## 快速开始

### 环境要求

- Python 3.11+
- pip 包管理器

### 安装

1. 克隆代码库
```bash
git clone https://github.com/TikHubIO/tkliveTools.git
cd tkliveTools
```

2. 安装依赖
```bash
pip install -r requirements.txt
```

3. 配置环境变量
```bash
cp .env.example .env
# 编辑.env文件，填入你的TIKHUB_API_KEY
```

### 运行服务

方式 1：使用便捷启动脚本（推荐）
```bash
python app.py
```

方式 2：使用 uvicorn 命令
```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

方式 3：生产环境多进程部署
```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 3
```

### 使用方法

连接WebSocket端点获取特定房间的消息：

```javascript
// 前端JavaScript示例
const roomId = "123456789"; // TikTok直播间ID
const ws = new WebSocket(`ws://localhost:8000/ws/${roomId}`);

ws.onmessage = (event) => {
  const message = JSON.parse(event.data);
  console.log("收到消息:", message);
};

ws.onclose = () => {
  console.log("WebSocket连接关闭");
};

ws.onerror = (error) => {
  console.error("WebSocket错误:", error);
};
```

## API文档

### WebSocket端点

#### `/ws/{room_id}`

建立WebSocket连接以接收指定直播间的消息。

- **参数**
  - `room_id`: TikTok直播间ID

- **返回数据**
  - 各类消息的JSON格式数据，包括：
    - 聊天消息 (WebcastChatMessage)
    - 礼物消息 (WebcastGiftMessage)
    - 点赞消息 (WebcastLikeMessage)
    - 用户进入消息 (WebcastMemberMessage)
    - 关注消息 (WebcastSocialMessage)
    - 观众排行榜 (WebcastRoomUserSeqMessage)
    - 连麦相关消息 (WebcastLinkMicMethod, WebcastLinkMessage, etc.)
    - 购物消息 (WebcastOecLiveShoppingMessage)
    - 等其他直播间互动消息

## 自定义消息处理

可以通过修改 main.py 中的 `wss_callbacks` 字典来自定义不同类型消息的处理方式：

```python
wss_callbacks = {
    "WebcastGiftMessage": crawler.WebcastGiftMessage,          # 礼物消息
    "WebcastChatMessage": crawler.WebcastChatMessage,          # 聊天消息
    "WebcastLikeMessage": crawler.WebcastLikeMessage,          # 点赞消息
    "WebcastMemberMessage": crawler.WebcastMemberMessage,      # 用户进入消息
    "WebcastSocialMessage": crawler.WebcastSocialMessage,      # 关注消息
    "WebcastRoomUserSeqMessage": crawler.WebcastRoomUserSeqMessage,  # 观众排行榜
    "WebcastLinkMicFanTicketMethod": crawler.WebcastLinkMicFanTicketMethod,  # 连麦粉丝票
    "WebcastLinkMicMethod": crawler.WebcastLinkMicMethod,       # 连麦消息
    "UserFanTicket": crawler.UserFanTicket,                   # 用户粉丝团消息
    "WebcastLinkMessage": crawler.WebcastLinkMessage,          # 连麦链接消息
    "WebcastLinkMicBattle": crawler.WebcastLinkMicBattle,      # 连麦对决
    "WebcastLinkLayerMessage": crawler.WebcastLinkLayerMessage,  # 连麦层信息
    "WebcastRoomMessage": crawler.WebcastRoomMessage,          # 直播间消息
    "WebcastOecLiveShoppingMessage": crawler.WebcastOecLiveShoppingMessage,  # 购物消息
    "broadcast": broadcast_callback,  # 广播回调
}
```

### 消息类型说明

| 消息类型 | 描述 | 包含数据示例 |
|---------|------|-------------|
| `WebcastChatMessage` | 聊天消息 | 用户昵称、消息内容 |
| `WebcastGiftMessage` | 礼物消息 | 用户昵称、礼物名称、礼物价值 |
| `WebcastLikeMessage` | 点赞消息 | 用户昵称、点赞数量 |
| `WebcastMemberMessage` | 用户进入消息 | 用户昵称、进入时间 |
| `WebcastSocialMessage` | 关注消息 | 用户昵称、关注动作 |
| `WebcastRoomUserSeqMessage` | 观众排行榜 | 在线观众排名信息 |
| `WebcastLinkMicFanTicketMethod` | 连麦粉丝票 | 粉丝票相关信息 |
| `WebcastLinkMicMethod` | 连麦消息 | 连麦操作信息 |
| `UserFanTicket` | 用户粉丝团 | 粉丝团相关信息 |
| `WebcastLinkMessage` | 连麦链接 | 连麦链接信息 |
| `WebcastLinkMicBattle` | 连麦对决 | 连麦对决信息 |
| `WebcastLinkLayerMessage` | 连麦层信息 | 连麦层级信息 |
| `WebcastRoomMessage` | 直播间消息 | 房间状态信息 |
| `WebcastOecLiveShoppingMessage` | 购物消息 | 商品信息、购买动作 |

### 错误处理

所有消息处理方法都采用统一的错误处理机制：
- **空数据检查**：当接收到空数据时，返回标准错误格式
- **异常捕获**：解析失败时返回详细的错误信息
- **日志记录**：所有操作都有相应的日志记录

错误返回格式：
```json
{
  "error": "错误类型描述",
  "details": "详细错误信息"
}
```

### 性能优化

- 所有消息处理方法都使用 `@classmethod` 装饰器提高性能
- 统一的错误处理减少重复代码
- 详细的日志记录便于调试和监控
- 标准化的返回格式便于客户端处理
