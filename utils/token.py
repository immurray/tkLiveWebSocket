from typing import Any, Dict, Optional

from log.logger import logger

from .client import APIClient


async def gen_ttwid(user_agent: Optional[str] = None) -> Optional[str]:
    """生成TikTokttwid"""
    try:
        ttwid = await APIClient.get(
            "/api/v1/tiktok/web/generate_ttwid", params={"user_agent": user_agent}
        )
        if not ttwid:
            logger.error("[GenTtwid] [❌ 获取ttwid失败] | [返回为空]")
            return None
        return ttwid.get("data", {}).get("ttwid")
    except Exception as e:
        logger.error(f"[GenTtwid] [❌ 获取ttwid异常] | [错误: {str(e)}]")
        return None


async def fetch_live_im_fetch(
    room_id: str, user_unique_id: Optional[str] = None, max_retries: int = 5
) -> Optional[Dict[str, Any]]:
    """获取直播信息，如果wrss为空则自动重试"""
    if not room_id:  # or not user_unique_id:
        logger.error("[FetchLiveImFetch] [❌ 参数无效] | [房间ID或用户ID为空]")
        return None

    retry_count = 0
    while retry_count < max_retries:
        response = await APIClient.get(
            "/api/v1/tiktok/web/fetch_live_im_fetch",
            params={"room_id": room_id, "user_unique_id": user_unique_id},
        )

        if response.get("code") == 200:
            data = response.get("data")
            wrss = data.get("routeParams", {}).get("wrss", "") if data else ""

            if wrss:
                logger.info(
                    f"[FetchLiveImFetch] [✅ 成功获取wrss] | [尝试次数：{retry_count + 1}]"
                )
                return data
            else:
                retry_count += 1
                logger.warning(
                    f"[FetchLiveImFetch] [⚠️ wrss为空，正在重试] | "
                    f"[重试次数：{retry_count}/{max_retries}]"
                )
                if retry_count < max_retries:
                    import asyncio

                    await asyncio.sleep(1)  # 等待1秒后重试
                continue
        else:
            logger.error(
                f"[FetchLiveImFetch] [❌ API返回错误] | "
                f"[code: {response.get('code')}, message: {response.get('message')}]"
            )
            return None

    logger.error(
        f"[FetchLiveImFetch] [❌ 达到最大重试次数] | "
        f"[重试{max_retries}次后wrss仍为空]"
    )
    return None


async def fetch_check_live_alive(room_id: str):
    """检查直播状态"""
    if not room_id:
        logger.error("[FetchCheckLiveAlive] [❌ 参数无效] | [房间ID列表为空]")
        return None

    response = await APIClient.get(
        "/api/v1/tiktok/web/fetch_check_live_alive",
        params={"room_id": room_id},
    )

    if response.get("code") == 200:
        return response.get("data")
    return None
