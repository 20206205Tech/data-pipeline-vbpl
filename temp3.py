from pathlib import Path

# Cấu hình ban đầu
folder_path = r"G:\My Drive\GitHubActions\data-pipeline-vbpl\prod\temp\New folder"
folder_path = (
    r"G:\My Drive\GitHubActions\data-pipeline-vbpl\prod\temp\New folder\New folder"
)
folder_path = r"G:\My Drive\GitHubActions\data-pipeline-vbpl\prod\temp\New folder (3)"
folder_path = r"G:\My Drive\GitHubActions\data-pipeline-vbpl\prod\temp\New folder (2)"
target_text = "Sorry, something went wrong"
max_lines = 200
deleted_count = 0

# 1. Thu thập danh sách file
print("Đang quét tìm file HTML...")
list_path = list(Path(folder_path).rglob("*.html"))
count = len(list_path)
print(f"Tổng số file HTML cần kiểm tra: {count}")
print("-" * 30)

# 2. Duyệt và kiểm tra từng file
for index, file_path in enumerate(list_path, start=1):
    print(f"Đang xử lý: {index}/{count} - Đường dẫn: {file_path}")
    should_delete = False

    try:
        # Mở và đọc file
        with open(file_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

            # Kiểm tra số lượng dòng và nội dung
            if len(lines) < max_lines:
                content = "".join(lines)
                if target_text in content:
                    should_delete = True

    except UnicodeDecodeError:
        print(f"  -> Bỏ qua file do lỗi định dạng (không phải UTF-8): {file_path.name}")
    except Exception as e:
        print(f"  -> Lỗi khi đọc file {file_path.name}: {e}")

    # 3. Thực hiện xóa file nếu đủ điều kiện
    if should_delete:
        try:
            file_path.unlink()
            print(f"  [X] Đã xóa: {file_path.name}")
            deleted_count += 1
        except Exception as e:
            print(f"  [!] Không thể xóa file {file_path.name}: {e}")

# Tổng kết
print("-" * 30)
print(f"Hoàn tất! Tổng cộng đã xóa {deleted_count} file HTML.")
