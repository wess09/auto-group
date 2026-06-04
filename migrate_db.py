import sqlite3
import os

def migrate():
    db_path = os.path.join("data", "auto_group.db")
    if not os.path.exists(db_path):
        print(f"数据库文件不存在: {db_path}")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # 尝试添加 ocr_enabled 列，默认值为 0 (False)
        cursor.execute("ALTER TABLE message_moderation_rules ADD COLUMN ocr_enabled BOOLEAN DEFAULT 0 NOT NULL")
        conn.commit()
        print("成功：已在 message_moderation_rules 表中添加 ocr_enabled 列。")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e):
            print("提示：ocr_enabled 列已经存在，无需重复添加。")
        else:
            print(f"发生错误: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    migrate()
