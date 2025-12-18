# tkLiveWebSocket 客户端连接示例

本文档提供了使用不同编程语言连接 tkLiveWebSocket WebSocket 服务的示例代码。

## 目录

- [Node.js 客户端示例](#nodejs-客户端示例)
- [Go 客户端示例](#go-客户端示例)
- [Java 客户端示例](#java-客户端示例)
- [Python 客户端示例](#python-客户端示例)
- [配置说明](#配置说明)

## Node.js 客户端示例

### 依赖配置

使用 npm:

```bash
npm install ws
```

或者使用 pnpm:

```bash
pnpm add ws
```

### 快速开始

```bash
# 进入示例目录
cd example/node

# 安装依赖
pnpm install

# 运行客户端 (替换为实际的房间ID)
node websocket-client.js 7514168917980400426

# 或者指定服务器地址
node websocket-client.js 7514168917980400426 ws://192.168.1.100:8000

# 启用调试模式查看所有消息
DEBUG=1 node websocket-client.js 7514168917980400426
```

### 示例代码

完整的客户端代码位于 `example/node/websocket-client.js`，支持事件驱动模式：

```javascript
const TikTokLiveClient = require('./websocket-client');

// 创建客户端实例
const client = new TikTokLiveClient({
    serverUrl: 'ws://localhost:8000',
    debug: true,                    // 启用调试模式
    heartbeatInterval: 30000,       // 心跳间隔 30 秒
    maxReconnectAttempts: 5,        // 最大重连次数
    autoReconnect: true             // 自动重连
});

// 监听聊天消息
client.on('chat', (data) => {
    console.log(`[弹幕] ${data.user.nickname}: ${data.content}`);
});

// 监听礼物消息
client.on('gift', (data) => {
    const giftName = data.gift.describe || data.gift.name || '未知礼物';
    console.log(`[礼物] ${data.user.nickname} 送出 ${giftName}`);
});

// 监听连接状态
client.on('status', (data) => {
    console.log(`[状态] ${data.message} (${data.step}/${data.total_steps})`);
});

// 监听错误
client.on('error', (err) => {
    console.error('[错误]', err.error || err.message);
});

// 连接到直播间
client.connect('7514168917980400426')
    .then(() => console.log('连接成功'))
    .catch(err => console.error('连接失败:', err));

// 优雅退出
process.on('SIGINT', () => {
    console.log('正在退出...');
    client.disconnect();
    process.exit(0);
});
```

### 可用事件

| 事件名 | 描述 | 回调参数 |
|--------|------|---------|
| `connect` | 连接成功 | `{ roomId }` |
| `disconnect` | 连接断开 | `{ code, reason }` |
| `error` | 发生错误 | `{ error, detail, suggestion }` |
| `reconnecting` | 正在重连 | `{ attempt, maxAttempts, delay }` |
| `status` | 状态更新 | `{ status, message, step, total_steps }` |
| `chat` | 聊天消息 | `{ user, content }` |
| `gift` | 礼物消息 | `{ user, gift }` |
| `rawMessage` | 原始消息 | 完整的 JSON 消息 |

## Go 客户端示例

### 依赖配置

使用 Go modules：

```bash
go mod init your-project
go get github.com/gorilla/websocket
```

### 快速开始

```bash
# 进入示例目录
cd example/go

# 运行客户端 (替换为实际的房间 ID)
go run main.go 7514168917980400426
```

### 示例代码

完整代码位于 `example/go/main.go`，支持交互式命令：

```go
package main

import (
    "fmt"
    "github.com/gorilla/websocket"
    "encoding/json"
    "net/url"
    "time"
)

type TikTokLiveClient struct {
    roomID    string
    serverURL string
    conn      *websocket.Conn
}

func NewClient(roomID, serverURL string) *TikTokLiveClient {
    if serverURL == "" {
        serverURL = "ws://localhost:8000"
    }
    return &TikTokLiveClient{roomID: roomID, serverURL: serverURL}
}

func (c *TikTokLiveClient) Connect() error {
    u, _ := url.Parse(fmt.Sprintf("%s/ws/%s", c.serverURL, c.roomID))
    conn, _, err := websocket.DefaultDialer.Dial(u.String(), nil)
    if err != nil {
        return err
    }
    c.conn = conn
    go c.readMessages()
    go c.heartbeat()
    return nil
}

func (c *TikTokLiveClient) readMessages() {
    for {
        _, message, err := c.conn.ReadMessage()
        if err != nil {
            fmt.Println("连接断开:", err)
            return
        }
        var msg map[string]interface{}
        json.Unmarshal(message, &msg)

        // 处理聊天消息
        if user, ok := msg["user"].(map[string]interface{}); ok {
            if content, ok := msg["content"].(string); ok {
                fmt.Printf("[弹幕] %s: %s\n", user["nickname"], content)
            }
        }
    }
}

func (c *TikTokLiveClient) heartbeat() {
    ticker := time.NewTicker(30 * time.Second)
    for range ticker.C {
        c.conn.WriteJSON(map[string]interface{}{
            "type": "ping",
            "timestamp": time.Now().UnixMilli(),
        })
    }
}

func main() {
    client := NewClient("7514168917980400426", "")
    if err := client.Connect(); err != nil {
        fmt.Println("连接失败:", err)
        return
    }
    select {} // 保持运行
}
```

### 可用命令

运行客户端后，可以输入以下命令：

| 命令 | 描述 |
|------|------|
| `ping` | 发送心跳包 |
| `close` | 关闭连接 |
| `quit` | 退出程序 |
| `help` | 显示帮助 |

## Java 客户端示例

### 依赖配置

使用 Maven:

```xml
<dependencies>
    <dependency>
        <groupId>org.java-websocket</groupId>
        <artifactId>Java-WebSocket</artifactId>
        <version>1.5.3</version>
    </dependency>
    <dependency>
        <groupId>org.json</groupId>
        <artifactId>json</artifactId>
        <version>20230227</version>
    </dependency>
</dependencies>
```

或者使用 Gradle:

```groovy
implementation 'org.java-websocket:Java-WebSocket:1.5.3'
implementation 'org.json:json:20230227'
```

### 示例代码

```java
import org.java_websocket.client.WebSocketClient;
import org.java_websocket.handshake.ServerHandshake;
import org.json.JSONObject;

import java.net.URI;
import java.net.URISyntaxException;
import java.util.HashMap;
import java.util.Map;

public class TikliveToolsClient {

    private WebSocketClient webSocketClient;
    private final String roomId;

    public TikliveToolsClient(String serverUrl, String roomId) {
        this.roomId = roomId;

        try {
            // 创建WebSocket连接URI，添加API密钥作为查询参数
            URI serverUri = new URI(serverUrl + "/ws/" + roomId);

            // 设置自定义头部（如果服务器支持头部认证方式）
            Map<String, String> headers = new HashMap<>();

            webSocketClient = new WebSocketClient(serverUri, headers) {
                @Override
                public void onOpen(ServerHandshake handshakedata) {
                    System.out.println("连接已打开，状态码: " + handshakedata.getHttpStatus());
                }

                @Override
                public void onMessage(String message) {
                    try {
                        // 解析JSON消息
                        JSONObject jsonMessage = new JSONObject(message);

                        // 根据消息类型处理
                        if (jsonMessage.has("content")) {
                            System.out.println("收到聊天消息: " + jsonMessage.getString("content"));
                        } else if (jsonMessage.has("status")) {
                            System.out.println("连接状态: " + jsonMessage.getString("status"));
                        } else {
                            System.out.println("收到直播消息: " + message);
                        }
                    } catch (Exception e) {
                        System.err.println("消息处理异常: " + e.getMessage());
                    }
                }

                @Override
                public void onClose(int code, String reason, boolean remote) {
                    System.out.println("连接已关闭, 代码: " + code + ", 原因: " + reason);
                    // 实现重连逻辑
                    if (remote) {
                        reconnect();
                    }
                }

                @Override
                public void onError(Exception ex) {
                    System.err.println("WebSocket连接异常: " + ex.getMessage());
                    ex.printStackTrace();
                }
            };
        } catch (URISyntaxException e) {
            System.err.println("URI语法错误: " + e.getMessage());
        }
    }

    public void connect() {
        if (webSocketClient != null) {
            webSocketClient.connect();
        }
    }

    public void disconnect() {
        if (webSocketClient != null && webSocketClient.isOpen()) {
            webSocketClient.close();
        }
    }

    public void reconnect() {
        try {
            System.out.println("尝试重新连接...");
            Thread.sleep(3000);  // 等待3秒后重连
            if (webSocketClient != null) {
                webSocketClient.reconnect();
            }
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
        }
    }

    public static void main(String[] args) {
        String serverUrl = "ws://your-server:8000"; // 替换为实际服务器地址
        String roomId = "7318296342189919011";  // 替换为实际的TikTok/抖音直播间ID

        TikliveToolsClient client = new TikliveToolsClient(serverUrl, roomId);
        client.connect();

        // 保持应用运行
        while (true) {
            try {
                Thread.sleep(10000);
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
                break;
            }
        }
    }
}
```

## Python 客户端示例

### 依赖配置

```bash
pip install websockets
```

### 示例代码

```python
import asyncio
import json
import websockets

class TikTokLiveClient:
    def __init__(self, room_id, server_url='ws://localhost:8000'):
        self.room_id = room_id
        self.server_url = server_url
        self.ws = None
        self.is_connected = False

    async def handle_message(self, message):
        try:
            data = json.loads(message)

            # 处理状态消息
            if 'status' in data:
                print(f"[状态] {data.get('message', data['status'])}")
                return

            # 处理心跳响应
            if data.get('type') == 'pong':
                print("[心跳] 服务器响应正常")
                return

            # 处理错误消息
            if 'error' in data:
                print(f"[错误] {data['error']}")
                if 'detail' in data:
                    print(f"[详情] {data['detail']}")
                return

            # 处理聊天消息
            if 'user' in data and 'content' in data:
                nickname = data['user'].get('nickname', '未知用户')
                print(f"[弹幕] {nickname}: {data['content']}")
                return

            # 其他消息
            print(f"[消息] {json.dumps(data, ensure_ascii=False)}")

        except json.JSONDecodeError:
            print(f"[解析失败] {message}")

    async def heartbeat(self):
        """每 30 秒发送心跳"""
        while self.is_connected:
            await asyncio.sleep(30)
            if self.is_connected and self.ws:
                await self.ws.send(json.dumps({
                    'type': 'ping',
                    'timestamp': int(asyncio.get_event_loop().time() * 1000)
                }))

    async def connect(self):
        url = f"{self.server_url}/ws/{self.room_id}"
        print(f"正在连接: {url}")

        try:
            async with websockets.connect(url) as ws:
                self.ws = ws
                self.is_connected = True
                print("[连接成功] WebSocket 已连接")

                # 启动心跳任务
                heartbeat_task = asyncio.create_task(self.heartbeat())

                try:
                    async for message in ws:
                        await self.handle_message(message)
                finally:
                    self.is_connected = False
                    heartbeat_task.cancel()

        except Exception as e:
            print(f"[连接错误] {e}")
            self.is_connected = False

    async def close(self):
        if self.ws:
            await self.ws.send(json.dumps({'action': 'close', 'type': 'close'}))
            await self.ws.close()


if __name__ == '__main__':
    client = TikTokLiveClient('7514168917980400426')
    try:
        asyncio.run(client.connect())
    except KeyboardInterrupt:
        print("\n正在退出...")
```

## 配置说明

tkLiveWebSocket 使用 TikHub API 进行数据采集，需要在服务端配置以下环境变量：

### 必需配置

1. **TIKHUB_API_KEY**: 您的 TikHub API 密钥
   - 获取方式：访问 [TikHub 官网](https://api.tikhub.io) 注册并获取 API 密钥
   - 配置方式：在服务器的 `.env` 文件中设置

2. **TIKHUB_BASE_URL**: TikHub API 基础 URL
   - 默认值：`https://api.tikhub.io`
   - 通常不需要修改

### 可选配置

3. **WSS_COOKIES**: WebSocket 连接所需的 Cookies
   - 用于某些特殊场景的认证
   - 大多数情况下不需要设置

### 连接格式

WebSocket 连接 URL 格式：
```
ws://your-server:8000/ws/{room_id}
```

其中：
- `your-server`: 部署服务的服务器地址
- `8000`: 服务端口（默认为 8000）
- `{room_id}`: TikTok 直播间 ID

### 如何获取房间 ID

**TikTok 直播间 ID 获取方法：**

1. 打开 TikTok 直播页面
2. 查看浏览器地址栏 URL，房间 ID 通常在 URL 中
3. 或者使用 TikHub API 的相关接口获取

### 注意事项

- 确保直播间正在直播中，否则无法连接
- 房间 ID 必须是有效的数字格式
- 服务器需要正确配置 TikHub API 密钥才能正常工作
- 建议在生产环境中使用 HTTPS/WSS 协议
- 客户端应实现心跳机制（建议每 30 秒发送一次 ping）
