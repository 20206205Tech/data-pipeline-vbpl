import os
from datetime import datetime

old_path = (
    r"C:\Users\Admin\Desktop\20206205\data-pipeline-vbpl\data\output_document_detail"
)

now = datetime.now().strftime("%Y_%m_%d_%H_%M_%S_%f")

new_path = f"{old_path}_{now}"

try:
    os.rename(old_path, new_path)
    print("✅ Đổi tên thư mục thành công!")
    print(f"Thư mục mới: {new_path}")
    os.makedirs(old_path, exist_ok=True)
    print("✅ Tạo lại thư mục gốc thành công!")
except FileNotFoundError:
    print(
        f"❌ Lỗi: Không tìm thấy thư mục gốc. Vui lòng kiểm tra lại đường dẫn:\n{old_path}"
    )
except PermissionError:
    print(
        "❌ Lỗi: Không có quyền truy cập hoặc thư mục đang được mở bởi một chương trình khác."
    )
except Exception as e:
    print(f"❌ Đã xảy ra lỗi: {e}")
