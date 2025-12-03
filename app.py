"""
TikTok Live WebSocket Server
启动脚本 - 便捷启动FastAPI服务器
"""

import uvicorn

from log.logger import logger
from utils.config import Config

if __name__ == "__main__":
    # 验证配置
    if not Config.validate():
        logger.error("[App] [❌ 配置验证失败] | [请检查.env文件中的配置]")
        exit(1)

    logger.info("[App] [🚀 启动TikTok直播WebSocket服务器]")
    logger.info(f"[App] [📡 API服务器] | [地址: {Config.TIKHUB_BASE_URL}]")
    logger.info("[App] [🌐 WebSocket端点] | [路径: ws://localhost:8000/ws/{{room_id}}]")
    logger.info("[App] [📖 访问文档] | [地址: http://localhost:8000/docs]")

    # 启动服务器
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,  # 开发模式下自动重载
        log_level="info",
    )
