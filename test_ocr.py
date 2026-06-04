import asyncio
import sys

# 解决 Windows 下的 Asyncio 报错提示
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from app.services.ocr import ocr_image_from_bytes
from PIL import Image, ImageDraw
import io

async def main():
    print("⏳ 开始测试 OCR 引擎，如果是第一次运行，后台会自动下载 PPOCR 模型（约 15MB）...")
    
    # 在内存中动态生成一张测试图片
    img = Image.new('RGB', (300, 100), color=(255, 255, 255))
    d = ImageDraw.Draw(img)
    # 不使用外部字体库，直接使用默认字体绘制英文和数字
    d.text((20, 40), "Hello PaddleOCR 123", fill=(0, 0, 0))
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    img_bytes = buf.getvalue()
    
    try:
        result = await ocr_image_from_bytes(img_bytes)
        print("\n✅ OCR 识别成功！提取的文字如下：")
        print("=" * 40)
        print(result)
        print("=" * 40)
    except Exception as e:
        import traceback
        print(f"\n❌ OCR 识别失败: {e}")
        print("\n完整错误堆栈：")
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
