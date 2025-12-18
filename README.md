# tkLiveWebSocket

tkLiveWebSocket 是一个高性能的 TikTok 直播弹幕和互动消息采集与转发服务。该服务建立与 TikTok 直播的 WebSocket 连接，实时获取直播间的聊天消息、礼物等互动数据，并通过 WebSocket 接口提供给客户端使用。

## 功能特点

- 实时采集 TikTok 直播间弹幕和互动消息
- 支持多房间同时监听，多客户端共享同一爬虫实例
- WebSocket 消息转发，便于前端实时展示
- 可扩展的消息处理回调机制
- 自动维护 WebSocket 连接和重连（最多 3 次重试）
- 自动清理无活跃连接的房间资源（5 分钟超时）
- 支持心跳检测，保持连接稳定

## 技术架构

- **后端框架**：FastAPI
- **WebSocket**：websockets
- **消息解析**：Protocol Buffers (protobuf)
- **HTTP 客户端**：httpx
- **日志系统**：自定义 logger

## 快速开始

### 环境要求

- Python 3.11+
- pip 包管理器

### 安装

1. 克隆代码库
```bash
git clone https://github.com/JohnserfSeed/tkLiveWebSocket.git
cd tkLiveWebSocket
```

2. 安装依赖
```bash
pip install -r requirements.txt
```

3. 配置环境变量
```bash
cp .env.example .env
# 编辑 .env 文件，填入你的 TIKHUB_API_KEY
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

连接 WebSocket 端点获取特定房间的消息：

```javascript
// 前端 JavaScript 示例
const roomId = "7514168917980400426"; // TikTok 直播间 ID
const ws = new WebSocket(`ws://localhost:8000/ws/${roomId}`);

ws.onmessage = (event) => {
  const message = JSON.parse(event.data);
  console.log("收到消息:", message);
};

ws.onclose = () => {
  console.log("WebSocket 连接关闭");
};

ws.onerror = (error) => {
  console.error("WebSocket 错误:", error);
};
```

## API 文档

### HTTP 端点

#### `GET /`

健康检查端点。

- **返回**：`{"msg": "Hello, TikHubIO!"}`

### WebSocket 端点

#### `WS /ws/{room_id}`

建立 WebSocket 连接以接收指定直播间的消息。

- **参数**
  - `room_id`: TikTok 直播间 ID

- **连接流程**
  1. `connecting` - 连接已建立，正在初始化
  2. `creating_crawler` - 正在创建直播爬虫实例
  3. `getting_token` - 正在获取访问令牌
  4. `checking_live` - 正在检查直播状态
  5. `connected` - 连接成功，等待接收消息

- **客户端消息格式**
  ```json
  // 心跳消息
  {"type": "ping", "timestamp": 1702345678000}

  // 关闭连接
  {"action": "close", "type": "close"}
  ```

- **服务端消息格式**
  ```json
  // 状态消息
  {"status": "connected", "message": "连接成功！", "step": 4, "total_steps": 4}

  // 心跳响应
  {"type": "pong", "timestamp": 1702345678000}

  // 聊天消息
  {"user": {"nickname": "用户名"}, "content": "消息内容"}

  // 错误消息
  {"error": "错误描述", "detail": "详细信息", "reconnect": true}
  ```

## 自定义消息处理

可以通过修改 `main.py` 中的 `wss_callbacks` 字典来自定义不同类型消息的处理方式：

```python
wss_callbacks = {
    "WebcastChatMessage": crawler.WebcastChatMessage,  # 聊天消息
    "broadcast": broadcast_callback,                    # 广播回调
}
```

### 消息类型说明

| 消息类型 | 描述 | 包含数据示例 |
|---------|------|-------------|
| `WebcastChatMessage` | 聊天消息 | 用户昵称、消息内容 |

### 错误处理

所有消息处理方法都采用统一的错误处理机制：
- **空数据检查**：当接收到空数据时，返回标准错误格式
- **异常捕获**：解析失败时返回详细的错误信息
- **日志记录**：所有操作都有相应的日志记录
- **自动重连**：网络异常时自动重试，最多 3 次

错误返回格式：
```json
{
  "error": "错误类型描述",
  "detail": "详细错误信息",
  "suggestion": "建议操作",
  "reconnect": true
}
```

## 客户端示例

项目提供了多种语言的客户端示例，详见 [examples.md](examples.md)：

- **Node.js**：完整的事件驱动客户端，支持心跳、自动重连
- **Go**：交互式命令行客户端，支持手动发送命令
- **Java**：基于 Java-WebSocket 的客户端示例
- **Python**：简单的 websocket-client 示例

示例代码位于 `example/` 目录下。

## 如何获取房间 ID

**TikTok 直播间 ID 获取方法：**

1. 打开 TikTok 直播页面
2. 查看浏览器地址栏 URL，房间 ID 通常在 URL 中
3. 或者使用 TikHub API 的相关接口获取
