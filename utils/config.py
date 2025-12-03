import os

import dotenv

from log.logger import logger

# 只在一个地方加载环境变量
dotenv.load_dotenv()


# 集中配置管理
class Config:
    # API配置
    TIKHUB_API_KEY = os.getenv("TIKHUB_API_KEY")
    TIKHUB_BASE_URL = os.getenv("TIKHUB_BASE_URL", "")
    WSS_COOKIES = os.getenv("WSS_COOKIES", "")

    # HTTP客户端配置
    HTTP_TIMEOUT = 60
    MAX_RETRIES = 3

    # WebSocket配置
    WS_TIMEOUT = 20

    @classmethod
    def validate(cls):
        """验证关键配置项"""
        if not cls.TIKHUB_API_KEY:
            logger.error("[Config] [❌ 配置错误] | [TIKHUB_API_KEY未设置]")
            return False
        return True
