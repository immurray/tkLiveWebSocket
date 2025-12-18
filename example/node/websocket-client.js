const WebSocket = require('ws');

/**
 * TikTok 直播 WebSocket 客户端
 * 作为组件使用，连接 TikliveTools 服务器并接收直播弹幕消息
 *
 * @example
 * const TikTokLiveClient = require('./websocket-client');
 *
 * const client = new TikTokLiveClient({
 *     serverUrl: 'ws://localhost:8000',
 *     debug: true
 * });
 *
 * client.on('chat', (data) => {
 *     console.log(`${data.user.nickname}: ${data.content}`);
 * });
 *
 * client.connect('7514168917980400426');
 */
class TikTokLiveClient {
    /**
     * 创建客户端实例
     * @param {Object} options - 配置选项
     * @param {string} [options.serverUrl='ws://localhost:8000'] - WebSocket 服务器地址
     * @param {boolean} [options.debug=false] - 调试模式
     * @param {number} [options.heartbeatInterval=30000] - 心跳间隔 (毫秒)
     * @param {number} [options.maxReconnectAttempts=5] - 最大重连次数
     * @param {number} [options.reconnectDelay=1000] - 重连延迟基数 (毫秒)
     * @param {boolean} [options.autoReconnect=true] - 是否自动重连
     */
    constructor(options = {}) {
        this.serverUrl = options.serverUrl || 'ws://localhost:8000';
        this.debug = options.debug || false;
        this.heartbeatInterval = options.heartbeatInterval || 30000;
        this.maxReconnectAttempts = options.maxReconnectAttempts || 5;
        this.reconnectDelay = options.reconnectDelay || 1000;
        this.autoReconnect = options.autoReconnect !== false;

        this.roomId = null;
        this.ws = null;
        this.isConnected = false;
        this.reconnectAttempts = 0;
        this.heartbeatTimer = null;
        this.connectionStartTime = null;

        // 事件回调
        this.callbacks = {
            // 连接事件
            connect: [],
            disconnect: [],
            error: [],
            reconnecting: [],

            // 状态事件
            status: [],

            // 直播消息事件
            chat: [],        // 弹幕消息
            gift: [],        // 礼物消息
            like: [],        // 点赞消息
            member: [],      // 进入直播间
            social: [],      // 关注/分享
            roomStats: [],   // 人数更新

            // 原始消息
            rawMessage: [],
        };

        // 消息统计
        this.stats = {
            chatMessages: 0,
            giftMessages: 0,
            likeMessages: 0,
            memberMessages: 0,
            socialMessages: 0,
            roomStatsMessages: 0,
            otherMessages: 0
        };
    }

    /**
     * 注册事件监听器
     * @param {string} event - 事件名称
     * @param {Function} callback - 回调函数
     * @returns {TikTokLiveClient} - 返回自身以支持链式调用
     */
    on(event, callback) {
        if (this.callbacks[event]) {
            this.callbacks[event].push(callback);
        }
        return this;
    }

    /**
     * 移除事件监听器
     * @param {string} event - 事件名称
     * @param {Function} callback - 回调函数
     * @returns {TikTokLiveClient}
     */
    off(event, callback) {
        if (this.callbacks[event]) {
            this.callbacks[event] = this.callbacks[event].filter(cb => cb !== callback);
        }
        return this;
    }

    /**
     * 触发事件
     * @private
     */
    _emit(event, data) {
        if (this.callbacks[event]) {
            this.callbacks[event].forEach(callback => {
                try {
                    callback(data);
                } catch (err) {
                    this._log('error', `Event callback error [${event}]:`, err.message);
                }
            });
        }
    }

    /**
     * 日志输出
     * @private
     */
    _log(level, ...args) {
        if (this.debug || level === 'error') {
            const timestamp = new Date().toLocaleTimeString('zh-CN', { hour12: false });
            console[level === 'error' ? 'error' : 'log'](`[${timestamp}]`, ...args);
        }
    }

    /**
     * 连接到直播间
     * @param {string} roomId - 直播间 ID
     * @returns {Promise<void>}
     */
    connect(roomId) {
        return new Promise((resolve, reject) => {
            if (!roomId) {
                const error = new Error('Room ID is required');
                reject(error);
                return;
            }

            this.roomId = roomId;
            const wsUrl = `${this.serverUrl}/ws/${this.roomId}`;
            this._log('info', `Connecting to: ${wsUrl}`);

            try {
                this.ws = new WebSocket(wsUrl);
            } catch (err) {
                reject(err);
                return;
            }

            this.ws.on('open', () => {
                this._log('info', 'WebSocket connected');
                this.isConnected = true;
                this.reconnectAttempts = 0;
                this.connectionStartTime = Date.now();
                this._startHeartbeat();
                this._emit('connect', { roomId: this.roomId });
                resolve();
            });

            this.ws.on('message', (data) => {
                try {
                    const message = JSON.parse(data.toString());
                    this._handleMessage(message);
                } catch (error) {
                    this._log('error', 'Parse message failed:', error.message);
                }
            });

            this.ws.on('close', (code, reason) => {
                const reasonStr = reason ? reason.toString() : '';
                this._log('info', `Disconnected | code: ${code} | reason: ${reasonStr}`);
                this.isConnected = false;
                this.connectionStartTime = null;
                this._stopHeartbeat();
                this._emit('disconnect', { code, reason: reasonStr });

                // 自动重连
                if (this.autoReconnect && code !== 1000 && this.reconnectAttempts < this.maxReconnectAttempts) {
                    this._reconnect();
                }
            });

            this.ws.on('error', (error) => {
                this._log('error', 'WebSocket error:', error.message);
                this._emit('error', error);
                reject(error);
            });
        });
    }

    /**
     * 处理接收到的消息
     * @private
     */
    _handleMessage(message) {
        // 触发原始消息事件
        this._emit('rawMessage', message);

        // 处理连接状态消息
        if (message.status) {
            this._emit('status', message);
            return;
        }

        // 处理心跳响应
        if (message.type === 'pong') {
            this._log('info', 'Heartbeat OK');
            return;
        }

        // 处理错误消息
        if (message.error) {
            this._emit('error', {
                error: message.error,
                detail: message.detail,
                suggestion: message.suggestion
            });
            return;
        }

        // 处理直播数据消息
        this._handleLiveMessage(message);
    }

    /**
     * 处理直播数据消息
     * @private
     */
    _handleLiveMessage(message) {
        // 聊天消息 (WebcastChatMessage)
        if (message.user && message.content) {
            this.stats.chatMessages++;
            this._emit('chat', message);
            return;
        }

        // 礼物消息 (WebcastGiftMessage)
        if (message.user && message.gift) {
            this.stats.giftMessages++;
            this._emit('gift', message);
            return;
        }

        // 点赞消息 (WebcastLikeMessage)
        if (message.user && (message.likeCount || message.like_count || message.total_like_count)) {
            this.stats.likeMessages++;
            this._emit('like', message);
            return;
        }

        // 进入直播间消息 (WebcastMemberMessage)
        if (message.user && message.action_id !== undefined) {
            this.stats.memberMessages++;
            this._emit('member', message);
            return;
        }

        // 关注/分享消息 (WebcastSocialMessage)
        if (message.user && (message.action === 1 || message.action === 3)) {
            this.stats.socialMessages++;
            this._emit('social', message);
            return;
        }

        // 观众人数更新 (WebcastRoomUserSeqMessage)
        if (message.total || message.total_user || message.viewer_count) {
            this.stats.roomStatsMessages++;
            this._emit('roomStats', message);
            return;
        }

        // 其他消息
        this.stats.otherMessages++;
        if (this.debug) {
            this._log('info', 'Other message:', JSON.stringify(message, null, 2));
        }
    }

    /**
     * 开始心跳
     * @private
     */
    _startHeartbeat() {
        this._stopHeartbeat();
        this.heartbeatTimer = setInterval(() => {
            if (this.isConnected) {
                this._sendPing();
            }
        }, this.heartbeatInterval);
    }

    /**
     * 停止心跳
     * @private
     */
    _stopHeartbeat() {
        if (this.heartbeatTimer) {
            clearInterval(this.heartbeatTimer);
            this.heartbeatTimer = null;
        }
    }

    /**
     * 发送心跳
     * @private
     */
    _sendPing() {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify({ type: 'ping', timestamp: Date.now() }));
        }
    }

    /**
     * 重连
     * @private
     */
    _reconnect() {
        this.reconnectAttempts++;
        const delay = this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1);

        this._log('info', `Reconnecting in ${delay / 1000}s... (${this.reconnectAttempts}/${this.maxReconnectAttempts})`);
        this._emit('reconnecting', { attempt: this.reconnectAttempts, maxAttempts: this.maxReconnectAttempts, delay });

        setTimeout(() => {
            this.connect(this.roomId).catch(() => {});
        }, delay);
    }

    /**
     * 断开连接
     */
    disconnect() {
        this.autoReconnect = false;
        this._stopHeartbeat();

        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            // 发送关闭请求
            this.ws.send(JSON.stringify({ action: 'close', type: 'close' }));
            this.ws.close(1000, 'Client disconnect');
        }

        this.isConnected = false;
    }

    /**
     * 获取连接时长 (秒)
     * @returns {number|null}
     */
    getConnectionDuration() {
        if (!this.connectionStartTime) return null;
        return Math.floor((Date.now() - this.connectionStartTime) / 1000);
    }

    /**
     * 获取消息统计
     * @returns {Object}
     */
    getStats() {
        return { ...this.stats };
    }

    /**
     * 重置消息统计
     */
    resetStats() {
        Object.keys(this.stats).forEach(key => {
            this.stats[key] = 0;
        });
    }
}

module.exports = TikTokLiveClient;
