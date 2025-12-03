import traceback
from typing import Any, Dict, Optional

import httpx
from tikhub import Client

from log.logger import logger

from .config import Config

# 创建tikhub客户端
tikhub_client = Client(
    base_url=Config.TIKHUB_BASE_URL,
    api_key=Config.TIKHUB_API_KEY,
    proxy=None,
    max_retries=Config.MAX_RETRIES,
    max_connections=50,
    timeout=Config.HTTP_TIMEOUT,
    max_tasks=50,
)

TikTokWeb = tikhub_client.TikTokWeb


# 创建HTTP客户端类
class APIClient:
    """统一API调用客户端"""

    @classmethod
    async def get(
        cls, endpoint: str, params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """执行GET请求"""
        try:
            async with httpx.AsyncClient(
                verify=False, timeout=Config.HTTP_TIMEOUT
            ) as client:
                response = await client.get(
                    f"{Config.TIKHUB_BASE_URL}{endpoint}",
                    params=params,
                    headers={"Authorization": Config.TIKHUB_API_KEY},
                )
                return cls._process_response(response, f"GET {endpoint}")
        except Exception as e:
            logger.error(
                f"[APIClient] [⚠️ GET请求异常] | [端点: {endpoint}] | [错误: {traceback.format_exc()}]"
            )
            return {"code": 500, "message": str(e), "data": None}

    @classmethod
    async def post(
        cls, endpoint: str, data: Any = None, json_data: Any = None
    ) -> Dict[str, Any]:
        """执行POST请求"""
        try:
            async with httpx.AsyncClient(
                verify=False, timeout=Config.HTTP_TIMEOUT
            ) as client:
                response = await client.post(
                    f"{Config.TIKHUB_BASE_URL}{endpoint}",
                    data=data,
                    json=json_data,
                    headers={"Authorization": Config.TIKHUB_API_KEY},
                )
                return cls._process_response(response, f"POST {endpoint}")
        except Exception as e:
            logger.error(
                f"[APIClient] [⚠️ POST请求异常] | [端点: {endpoint}] | [错误: {str(e)}]"
            )
            return {"code": 500, "message": str(e), "data": None}

    @staticmethod
    def _process_response(
        response: httpx.Response, request_desc: str
    ) -> Dict[str, Any]:
        """处理API响应"""
        try:
            if response.status_code == 200:
                data = response.json()
                if data.get("code") == 200:
                    return data
                else:
                    logger.error(
                        f"[APIClient] [❌ API错误] | [{request_desc}] | [信息: {data.get('message')}]"
                    )
                    return data
            else:
                logger.info(response.url)
                logger.error(
                    f"[APIClient] [❌ 请求失败] | [{request_desc}] | [状态码: {response.status_code}] | [响应: {response.text}]"
                )
                return {
                    "code": response.status_code,
                    "message": response.text,
                    "data": None,
                }
        except Exception as e:
            logger.error(
                f"[APIClient] [⚠️ 响应处理错误] | [{request_desc}] | [错误: {str(e)}]"
            )
            return {"code": 500, "message": str(e), "data": None}
