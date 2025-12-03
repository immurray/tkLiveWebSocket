package main

import (
    "bufio"
    "context"
    "encoding/json"
    "fmt"
    "log"
    "net/url"
    "os"
    "os/signal"
    "strconv"
    "strings"
    "syscall"
    "time"

    "github.com/gorilla/websocket"
)

type Message struct {
    Status      string `json:"status,omitempty"`
    Type        string `json:"type,omitempty"`
    Action      string `json:"action,omitempty"`
    Message     string `json:"message,omitempty"`
    Step        int    `json:"step,omitempty"`
    TotalSteps  int    `json:"total_steps,omitempty"`
    Timestamp   int64  `json:"timestamp,omitempty"`
    Error       string `json:"error,omitempty"`
    Detail      string `json:"detail,omitempty"`
    Suggestion  string `json:"suggestion,omitempty"`
    User        *User  `json:"user,omitempty"`
    Gift        *Gift  `json:"gift,omitempty"`
    PongCount   int    `json:"pong_count,omitempty"`
    Duration    string `json:"connection_duration,omitempty"`
    Details     string `json:"details,omitempty"`
    Reconnect   bool   `json:"reconnect,omitempty"`
}

type User struct {
    Nickname string `json:"nickname"`
}

type Gift struct {
    Describe     string `json:"describe"`
    DiamondCount int    `json:"diamondCount"`
}

type TikTokLiveClient struct {
    roomID               string
    serverURL            string
    conn                 *websocket.Conn
    isConnected          bool
    reconnectAttempts    int
    maxReconnectAttempts int
    reconnectDelay       time.Duration
    ctx                  context.Context
    cancel               context.CancelFunc
    heartbeatTicker      *time.Ticker
}

func NewTikTokLiveClient(roomID, serverURL string) *TikTokLiveClient {
    if serverURL == "" {
        serverURL = "ws://localhost:8000"
    }

    ctx, cancel := context.WithCancel(context.Background())

    return &TikTokLiveClient{
        roomID:               roomID,
        serverURL:            serverURL,
        isConnected:          false,
        reconnectAttempts:    0,
        maxReconnectAttempts: 5,
        reconnectDelay:       time.Second,
        ctx:                  ctx,
        cancel:               cancel,
    }
}

func (c *TikTokLiveClient) Connect() error {
    u, err := url.Parse(fmt.Sprintf("%s/ws/%s", c.serverURL, c.roomID))
    if err != nil {
        return fmt.Errorf("解析URL失败: %v", err)
    }

    fmt.Printf("🔗 正在连接到: %s\n", u.String())

    dialer := websocket.Dialer{
        HandshakeTimeout: 10 * time.Second,
    }

    conn, _, err := dialer.Dial(u.String(), nil)
    if err != nil {
        return fmt.Errorf("连接失败: %v", err)
    }

    c.conn = conn
    c.isConnected = true
    c.reconnectAttempts = 0

    fmt.Println("✅ WebSocket 连接已建立")

    // 启动心跳
    c.startHeartbeat()

    // 启动消息监听
    go c.readMessages()

    return nil
}

func (c *TikTokLiveClient) readMessages() {
    defer func() {
        c.isConnected = false
        if c.heartbeatTicker != nil {
            c.heartbeatTicker.Stop()
        }
    }()

    for {
        select {
        case <-c.ctx.Done():
            return
        default:
            _, messageData, err := c.conn.ReadMessage()
            if err != nil {
                if websocket.IsUnexpectedCloseError(err, websocket.CloseGoingAway, websocket.CloseAbnormalClosure) {
                    log.Printf("❌ WebSocket 错误: %v", err)
                }
                fmt.Printf("🔌 连接已关闭: %v\n", err)

                // 尝试重连
                if c.reconnectAttempts < c.maxReconnectAttempts {
                    go c.reconnect()
                }
                return
            }

            var message Message
            if err := json.Unmarshal(messageData, &message); err != nil {
                log.Printf("❌ 解析消息失败: %v", err)
                log.Printf("原始消息: %s", string(messageData))
                continue
            }

            c.handleMessage(message)
        }
    }
}

func (c *TikTokLiveClient) handleMessage(message Message) {
    timestamp := time.Now().Format("15:04:05")

    switch message.Status {
    case "connecting", "creating_crawler", "getting_token", "checking_live", "getting_live_info":
        fmt.Printf("📡 [%s] %s (%d/%d)\n", timestamp, message.Message, message.Step, message.TotalSteps)
    case "connected":
        fmt.Printf("🎉 [%s] %s\n", timestamp, message.Message)
    case "closing":
        fmt.Printf("🔄 [%s] %s\n", timestamp, message.Message)
    default:
        switch message.Type {
        case "pong":
            fmt.Printf("💗 [%s] 心跳正常 - %s\n", timestamp, message.Message)
            if message.Duration != "" {
                fmt.Printf("⏱️  连接时长: %s\n", message.Duration)
            }
        case "server_activity":
            fmt.Printf("📊 [%s] 服务器活动: %s\n", timestamp, message.Details)
        default:
            // 处理礼物消息或其他数据
            if message.User != nil && message.Gift != nil {
                user := message.User.Nickname
                if user == "" {
                    user = "未知用户"
                }
                gift := message.Gift.Describe
                if gift == "" {
                    gift = "未知礼物"
                }
                price := message.Gift.DiamondCount
                fmt.Printf("🎁 [%s] %s 送出了 %s (价值 %d 钻石)\n", timestamp, user, gift, price)
            } else if message.Error != "" {
                fmt.Printf("❌ [%s] 错误: %s\n", timestamp, message.Error)
                fmt.Printf("📄 详情: %s\n", message.Detail)
                if message.Suggestion != "" {
                    fmt.Printf("💡 建议: %s\n", message.Suggestion)
                }
            } else {
                // 打印其他类型的消息
                messageJSON, _ := json.MarshalIndent(message, "", "  ")
                fmt.Printf("📨 [%s] 收到消息:\n%s\n", timestamp, string(messageJSON))
            }
        }
    }
}

func (c *TikTokLiveClient) startHeartbeat() {
    // 每30秒发送一次心跳
    c.heartbeatTicker = time.NewTicker(30 * time.Second)
    go func() {
        for {
            select {
            case <-c.ctx.Done():
                return
            case <-c.heartbeatTicker.C:
                if c.isConnected {
                    c.sendPing()
                }
            }
        }
    }()
}

func (c *TikTokLiveClient) sendPing() {
    if !c.isConnected || c.conn == nil {
        return
    }

    pingMessage := Message{
        Type:      "ping",
        Timestamp: time.Now().UnixMilli(),
    }

    data, err := json.Marshal(pingMessage)
    if err != nil {
        log.Printf("❌ 序列化心跳消息失败: %v", err)
        return
    }

    if err := c.conn.WriteMessage(websocket.TextMessage, data); err != nil {
        log.Printf("❌ 发送心跳失败: %v", err)
        return
    }

    fmt.Println("📤 发送心跳包")
}

func (c *TikTokLiveClient) sendClose() {
    if !c.isConnected || c.conn == nil {
        return
    }

    closeMessage := Message{
        Action: "close",
        Type:   "close",
    }

    data, err := json.Marshal(closeMessage)
    if err != nil {
        log.Printf("❌ 序列化关闭消息失败: %v", err)
        return
    }

    fmt.Println("📤 发送关闭请求...")
    if err := c.conn.WriteMessage(websocket.TextMessage, data); err != nil {
        log.Printf("❌ 发送关闭消息失败: %v", err)
    }
}

func (c *TikTokLiveClient) reconnect() {
    c.reconnectAttempts++
    delay := c.reconnectDelay * time.Duration(1<<uint(c.reconnectAttempts-1))

    fmt.Printf("🔄 %v后尝试重连... (%d/%d)\n", delay, c.reconnectAttempts, c.maxReconnectAttempts)

    time.Sleep(delay)

    if err := c.Connect(); err != nil {
        log.Printf("❌ 重连失败: %v", err)
        if c.reconnectAttempts < c.maxReconnectAttempts {
            go c.reconnect()
        }
    }
}

func (c *TikTokLiveClient) Close() {
    c.cancel()

    if c.heartbeatTicker != nil {
        c.heartbeatTicker.Stop()
    }

    if c.isConnected && c.conn != nil {
        c.sendClose()
        time.Sleep(time.Second) // 等待关闭消息发送
        c.conn.Close()
    }
}

func (c *TikTokLiveClient) handleCommands() {
    fmt.Println("\n📋 可用命令:")
    fmt.Println("  ping  - 发送心跳包")
    fmt.Println("  close - 关闭连接")
    fmt.Println("  quit  - 退出程序")
    fmt.Println("  help  - 显示帮助\n")

    scanner := bufio.NewScanner(os.Stdin)
    for scanner.Scan() {
        command := strings.TrimSpace(strings.ToLower(scanner.Text()))

        switch command {
        case "ping":
            c.sendPing()
        case "close":
            c.sendClose()
        case "quit", "exit":
            fmt.Println("👋 正在退出...")
            if c.isConnected {
                c.sendClose()
            }
            time.Sleep(time.Second)
            c.Close()
            os.Exit(0)
        case "help":
            fmt.Println("\n📋 可用命令:")
            fmt.Println("  ping  - 发送心跳包")
            fmt.Println("  close - 关闭连接")
            fmt.Println("  quit  - 退出程序")
            fmt.Println("  help  - 显示帮助\n")
        case "":
            // 忽略空输入
        default:
            fmt.Printf("❓ 未知命令: %s. 输入 'help' 查看可用命令.\n", command)
        }
    }
}

func main() {
    if len(os.Args) < 2 {
        fmt.Println("❌ 请提供房间ID")
        fmt.Println("使用方法: go run main.go <房间ID>")
        fmt.Println("示例: go run main.go 7514168917980400426")
        os.Exit(1)
    }

    roomID := os.Args[1]

    // 验证房间ID是否为数字
    if _, err := strconv.Atoi(roomID); err != nil {
        fmt.Printf("❌ 无效的房间ID: %s (必须是数字)\n", roomID)
        os.Exit(1)
    }

    fmt.Println("🚀 启动 TikTok 直播客户端")
    fmt.Printf("📍 房间ID: %s\n", roomID)

    client := NewTikTokLiveClient(roomID, "")

    // 连接到服务器
    if err := client.Connect(); err != nil {
        log.Fatalf("❌ 连接失败: %v", err)
    }

    // 设置优雅退出
    sigChan := make(chan os.Signal, 1)
    signal.Notify(sigChan, syscall.SIGINT, syscall.SIGTERM)

    go func() {
        <-sigChan
        fmt.Println("\n🛑 收到中断信号，正在优雅退出...")
        client.Close()
        os.Exit(0)
    }()

    // 处理用户命令
    client.handleCommands()
}