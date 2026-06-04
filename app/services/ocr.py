"""PaddleOCR (PPOCRv5) 图片文字识别服务。

全局单例延迟初始化 PaddleOCR 引擎，所有推理通过 asyncio.to_thread()
在线程池中执行，不阻塞事件循环。
"""

import asyncio
import logging
import threading
from io import BytesIO

import httpx
import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)

_ocr_instance = None
_ocr_lock = threading.Lock()

# 下载图片超时秒数
_DOWNLOAD_TIMEOUT = 15.0


def _get_ocr():
    """获取全局 RapidOCR 单例，首次调用时初始化（线程安全）。"""
    global _ocr_instance
    if _ocr_instance is not None:
        return _ocr_instance
    with _ocr_lock:
        if _ocr_instance is not None:
            return _ocr_instance
        
        from rapidocr_onnxruntime import RapidOCR

        _ocr_instance = RapidOCR(
            text_score=0.3,
            use_angle_cls=False,  # 不识别倒立文本，加快速度
        )
        return _ocr_instance


def _ocr_from_ndarray(img_array: np.ndarray) -> str:
    """对 numpy 数组执行 OCR 推理，返回拼接后的全文。"""
    ocr = _get_ocr()
    result, elapse = ocr(img_array)
    if not result:
        return ""
    lines: list[str] = []
    for item in result:
        # item 结构: (box, text, score)
        if isinstance(item, (list, tuple)) and len(item) >= 2:
            text = str(item[1]).strip()
            if text:
                lines.append(text)
    return "\n".join(lines)


def _bytes_to_ndarray(data: bytes) -> np.ndarray:
    """将图片 bytes 转换为 numpy 数组（RGB）。"""
    img = Image.open(BytesIO(data))
    if img.mode != "RGB":
        img = img.convert("RGB")
    return np.array(img)


async def ocr_image_from_bytes(data: bytes) -> str:
    """从内存 bytes 识别图片文字。

    在线程池中执行推理，不阻塞事件循环。
    """
    img_array = _bytes_to_ndarray(data)
    return await asyncio.to_thread(_ocr_from_ndarray, img_array)


async def ocr_image_from_url(url: str) -> str:
    """下载图片并执行 OCR。"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    async with httpx.AsyncClient(timeout=_DOWNLOAD_TIMEOUT, headers=headers) as client:
        try:
            resp = await client.get(url)
            resp.raise_for_status()
            img_bytes = resp.content
        except httpx.HTTPError as e:
            from nonebot import logger
            logger.warning(f"下载图片失败 (可能被 QQ 拦截或过期) URL: {url}, 错误: {e}")
            return ""
    return await ocr_image_from_bytes(img_bytes)
