const WebSocket = require('ws');
const readline = require('readline');

class TikTokLiveClient {
    constructor(roomId, serverUrl = 'ws://localhost:8000') {
        this.roomId = roomId;
        this.serverUrl = serverUrl;
        this.ws = null;
        this.isConnected = false;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 5;
        this.reconnectDelay = 1000; // 1秒

        // 创建命令行接口
        this.rl = readline.createInterface({
            input: process.stdin,
            output: process.stdout
        });

        this.setupCommands();
    }

    connect() {
        const wsUrl = `${this.serverUrl}/ws/${this.roomId}`;
        console.log(`🔗 正在连接到: ${wsUrl}`);

        this.ws = new WebSocket(wsUrl);

        this.ws.on('open', () => {
            console.log('✅ WebSocket 连接已建立');
            this.isConnected = true;
            this.reconnectAttempts = 0;

            // 开始心跳
            this.startHeartbeat();
        });

        this.ws.on('message', (data) => {
            try {
                const message = JSON.parse(data.toString());
                this.handleMessage(message);
            } catch (error) {
                console.error('❌ 解析消息失败:', error);
                console.log('原始消息:', data.toString());
            }
        });

        this.ws.on('close', (code, reason) => {
            console.log(`🔌 连接已关闭 [代码: ${code}] [原因: ${reason || '无'}]`);
            this.isConnected = false;

            if (this.heartbeatInterval) {
                clearInterval(this.heartbeatInterval);
                this.heartbeatInterval = null;
            }

            // 自动重连（除非是主动关闭）
            if (code !== 1000 && this.reconnectAttempts < this.maxReconnectAttempts) {
                this.reconnect();
            }
        });

        this.ws.on('error', (error) => {
            console.error('❌ WebSocket 错误:', error.message);
        });
    }

    handleMessage(message) {
        const timestamp = new Date().toLocaleTimeString();

        switch (message.status || message.type) {
            case 'connecting':
            case 'creating_crawler':
            case 'getting_token':
            case 'checking_live':
            case 'getting_live_info':
                console.log(`📡 [${timestamp}] ${message.message} (${message.step}/${message.total_steps})`);
                break;

            case 'connected':
                console.log(`🎉 [${timestamp}] ${message.message}`);
                break;

            case 'pong':
                console.log(`💗 [${timestamp}] 心跳正常 - ${message.message}`);
                if (message.connection_duration) {
                    console.log(`⏱️  连接时长: ${message.connection_duration}`);
                }
                break;

            case 'server_activity':
                console.log(`📊 [${timestamp}] 服务器活动: ${message.details}`);
                break;

            case 'closing':
                console.log(`🔄 [${timestamp}] ${message.message}`);
                break;

            default:
                // 处理礼物消息或其他数据
                if (message.user && message.gift) {
                    const user = message.user.nickname || '未知用户';
                    const gift = message.gift.describe || '未知礼物';
                    const price = message.gift.diamondCount || 0;
                    console.log(`🎁 [${timestamp}] ${user} 送出了 ${gift} (价值 ${price} 钻石)`);
                } else if (message.error) {
                    console.error(`❌ [${timestamp}] 错误: ${message.error}`);
                    console.error(`📄 详情: ${message.detail}`);
                    if (message.suggestion) {
                        console.log(`💡 建议: ${message.suggestion}`);
                    }
                } else {
                    console.log(`📨 [${timestamp}] 收到消息:`, JSON.stringify(message, null, 2));
                }
                break;
        }
    }

    startHeartbeat() {
        // 每30秒发送一次心跳
        this.heartbeatInterval = setInterval(() => {
            if (this.isConnected) {
                this.sendPing();
            }
        }, 30000);
    }

    sendPing() {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            const pingMessage = {
                type: 'ping',
                timestamp: Date.now()
            };
            this.ws.send(JSON.stringify(pingMessage));
            console.log('📤 发送心跳包');
        }
    }

    sendClose() {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            const closeMessage = {
                action: 'close',
                type: 'close'
            };
            console.log('📤 发送关闭请求...');
            this.ws.send(JSON.stringify(closeMessage));
        }
    }

    reconnect() {
        this.reconnectAttempts++;
        const delay = this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1);

        console.log(`🔄 ${delay / 1000}秒后尝试重连... (${this.reconnectAttempts}/${this.maxReconnectAttempts})`);

        setTimeout(() => {
            this.connect();
        }, delay);
    }

    setupCommands() {
        console.log('\n📋 可用命令:');
        console.log('  ping  - 发送心跳包');
        console.log('  close - 关闭连接');
        console.log('  quit  - 退出程序');
        console.log('  help  - 显示帮助\n');

        this.rl.on('line', (input) => {
            const command = input.trim().toLowerCase();

            switch (command) {
                case 'ping':
                    this.sendPing();
                    break;

                case 'close':
                    this.sendClose();
                    break;

                case 'quit':
                case 'exit':
                    console.log('👋 正在退出...');
                    if (this.isConnected) {
                        this.sendClose();
                    }
                    setTimeout(() => {
                        process.exit(0);
                    }, 1000);
                    break;

                case 'help':
                    this.setupCommands();
                    break;

                case '':
                    // 忽略空输入
                    break;

                default:
                    console.log(`❓ 未知命令: ${command}. 输入 'help' 查看可用命令.`);
                    break;
            }
        });
    }

    close() {
        if (this.heartbeatInterval) {
            clearInterval(this.heartbeatInterval);
        }

        if (this.ws) {
            this.ws.close(1000, 'Client initiated close');
        }

        this.rl.close();
    }
}

// 使用示例
function main() {
    const roomId = process.argv[2];

    if (!roomId) {
        console.error('❌ 请提供房间ID');
        console.log('使用方法: node websocket-client.js <房间ID>');
        console.log('示例: node websocket-client.js 7514168917980400426');
        process.exit(1);
    }

    console.log(`🚀 启动 TikTok 直播客户端`);
    console.log(`📍 房间ID: ${roomId}`);

    const client = new TikTokLiveClient(roomId);
    client.connect();

    // 优雅退出处理
    process.on('SIGINT', () => {
        console.log('\n🛑 收到中断信号，正在优雅退出...');
        client.close();
        process.exit(0);
    });
}

if (require.main === module) {
    main();
}

module.exports = TikTokLiveClient;

