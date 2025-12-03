## examples.md 文档

# TikliveTools 客户端连接示例

本文档提供了使用不同编程语言连接 TikliveTools WebSocket 服务的示例代码。

## 目录

- [Java 客户端示例](#java-客户端示例)
- [鉴权说明](#鉴权说明)

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

## 鉴权说明

TikliveTools 使用 TikHub API 进行数据采集，需要配置以下环境变量：

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
- `your-server`: 部署 TikliveTools 的服务器地址
- `8000`: 服务端口（默认为 8000）
- `{room_id}`: TikTok/抖音直播间 ID

### 示例连接

```javascript
// JavaScript 示例
const ws = new WebSocket('ws://localhost:8000/ws/7318296342189919011');

ws.onmessage = function(event) {
    const data = JSON.parse(event.data);
    console.log('收到消息:', data);
};
```

```python
# Python 示例
import websocket
import json

def on_message(ws, message):
    data = json.loads(message)
    print(f"收到消息: {data}")

ws = websocket.WebSocketApp("ws://localhost:8000/ws/7318296342189919011",
                           on_message=on_message)
ws.run_forever()
```

### 如何获取房间ID

**TikTok直播间ID获取方法：**

1. 打开TikTok直播页面
2. 查看浏览器地址栏URL，房间ID通常在URL中
3. 或者使用TikHub API的相关接口获取

**抖音直播间ID获取方法：**

1. 打开抖音直播页面（网页版或手机分享链接）
2. 房间ID通常在URL参数中，格式类似 `room_id=7318296342189919011`
3. 也可以通过抖音开放平台API获取

### 注意事项

- 确保直播间正在直播中，否则可能无法连接
- 房间ID必须是有效的数字格式
- 服务器需要正确配置TikHub API密钥才能正常工作
- 建议在生产环境中使用HTTPS/WSS协议
