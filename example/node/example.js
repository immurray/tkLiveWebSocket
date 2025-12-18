/**
 * TikTokLiveClient Usage Example
 */
const TikTokLiveClient = require('./websocket-client');

// Create client instance
const client = new TikTokLiveClient({
    serverUrl: 'ws://localhost:8000',
    debug: true,
    autoReconnect: true
});

// Register event listeners
client
    .on('connect', ({ roomId }) => {
        console.log(`Connected to room: ${roomId}`);
    })
    .on('disconnect', ({ code, reason }) => {
        console.log(`Disconnected: ${code} - ${reason}`);
    })
    .on('status', (data) => {
        console.log(`[Status] ${data.message || data.status}`);
    })
    .on('chat', (data) => {
        const nickname = data.user?.nickname || 'Unknown';
        console.log(`[Chat] ${nickname}: ${data.content}`);
    })
    .on('gift', (data) => {
        const nickname = data.user?.nickname || 'Unknown';
        const giftName = data.gift?.name || data.gift?.describe || 'Unknown';
        const count = data.repeat_count || 1;
        console.log(`[Gift] ${nickname} sent ${giftName} x${count}`);
    })
    .on('like', (data) => {
        const nickname = data.user?.nickname || 'Unknown';
        const count = data.likeCount || data.like_count || 1;
        console.log(`[Like] ${nickname} liked x${count}`);
    })
    .on('member', (data) => {
        const nickname = data.user?.nickname || 'Unknown';
        console.log(`[Join] ${nickname} joined`);
    })
    .on('social', (data) => {
        const nickname = data.user?.nickname || 'Unknown';
        const action = data.action === 1 ? 'followed' : 'shared';
        console.log(`[Social] ${nickname} ${action}`);
    })
    .on('roomStats', (data) => {
        const count = data.total || data.total_user || data.viewer_count;
        console.log(`[Viewers] ${count}`);
    })
    .on('error', (err) => {
        console.error('[Error]', err.error || err.message);
    });

// Get room ID from command line or use default
const roomId = process.argv[2] || '7584070561976503061';

// Connect
client.connect(roomId)
    .then(() => {
        console.log('Connection established');
    })
    .catch((err) => {
        console.error('Connection failed:', err.message);
    });

// Graceful shutdown
process.on('SIGINT', () => {
    console.log('\nDisconnecting...');
    console.log('Stats:', client.getStats());
    client.disconnect();
    process.exit(0);
});
