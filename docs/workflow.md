<!-- Các bản ghi đang ở bước khác (ví dụ bước 5) nhưng bản cũ thì giờ làm như thế nào ? -->

Đối phó với các bản ghi đang xử lý dang dở (mid-flight records) khi hệ thống nâng cấp phiên bản phụ thuộc vào việc **sự thay đổi của version 2.0 nằm ở đâu** so với vị trí hiện tại của bản ghi (bước 5).

Hệ thống hiện tại có thể giải quyết bài toán này theo 3 kịch bản:

### Kịch bản 1: Kế thừa tự động (Không cần làm gì cả)

**Khi nào áp dụng:** Phiên bản mới chỉ thêm các bước ở phía sau (ví dụ thêm bước 15, 16) hoặc cập nhật logic code của các bước từ số 6 trở đi.

**Cơ chế tự chữa lành (Self-healing):**
Hàm `fetch_and_lock_pending_tasks` trong hệ thống không giới hạn việc tìm kiếm theo `pipeline_version`. Nó chỉ quan tâm đến việc: _"Có bản ghi nào đã xong bước 5 (`end_time IS NOT NULL`) để nhét vào bước 6 không?"_.

Do đó, khi script của bước 6 chạy với code mới:

1. Nó tự động hút các bản ghi version 1.0 đang đợi ở bước 5 vào xử lý.
2. Khi xử lý xong, hàm `log_workflow_state` sẽ lưu trạng thái mới vào database. Vì code đang chạy là version 2.0 (lấy từ `workflow_config`), cột `pipeline_version` trong database sẽ tự động được ghi đè (upsert) thành `'2.0'`.

Toàn bộ các bản ghi cũ sẽ tự động "tiến hóa" thành version mới khi chúng di chuyển qua trạm tiếp theo mà không cần bất kỳ câu lệnh SQL nào.

### Kịch bản 2: Bị lỡ trạm (Kéo lùi bản ghi)

**Khi nào áp dụng:** Bản cập nhật 2.0 có chèn thêm một bước xử lý dữ liệu hoàn toàn mới nằm ở TRƯỚC bước 5 (ví dụ: một bước 4.5 để dịch text). Các bản ghi đang ở bước 5 đã vô tình bỏ lỡ khâu quan trọng này.

**Cách giải quyết:** Lùi trạng thái của các bản ghi này về ngay trước điểm rẽ nhánh để chúng chạy qua luồng mới.

```sql
UPDATE "TÊN_DATASET"."t_document_state"
SET
    workflow_id = 4,             -- Kéo lùi về bước 4
    end_time = NOW(),            -- Đánh dấu hoàn thành bước 4 để bước mới (4.5) có thể nhặt
    pipeline_version = '2.0'     -- Ép lên version mới
WHERE pipeline_version = '1.0'
  AND workflow_id >= 5;          -- Áp dụng cho những bản ghi đã đi quá điểm rẽ nhánh
```

### Kịch bản 3: Reset toàn diện (Chạy lại từ đầu)

**Khi nào áp dụng:** Version 2.0 thay đổi cấu trúc cốt lõi (ví dụ: đổi thư viện bóc tách HTML ở bước 6, thay đổi logic cào list ở bước 4). Mọi bản ghi dù đang ở bước 5, 10 hay 14 đều phải xử lý lại để đảm bảo tính đồng nhất của kho dữ liệu.

**Cách giải quyết:** Đẩy toàn bộ hệ thống về vạch xuất phát (ví dụ lùi về bước 3 - đã có sẵn danh sách tổng, chuẩn bị chạy cào list chi tiết).

```sql
UPDATE "TÊN_DATASET"."t_document_state"
SET
    workflow_id = 3,
    end_time = NOW(),
    pipeline_version = '2.0'
WHERE pipeline_version = '1.0';
```

_Điểm tối ưu:_ Ngay cả khi bạn ép hệ thống chạy lại từ đầu, nhờ cơ chế kiểm tra mã băm (`get_existing_hash_from_db`) đã được thiết kế sẵn, các file HTML hay Markdown không có sự thay đổi về nội dung text sẽ lập tức được bỏ qua công đoạn upload API lên Google Drive. Quá trình quét lại dữ liệu cũ sẽ diễn ra cực kỳ nhanh chóng.
