CHUNKING_PROMPT = """
Bạn là một chuyên gia phân chia văn bản (Semantic Chunker) cho hệ thống tìm kiếm.
Nhiệm vụ của bạn là gộp các đoạn văn bản nhỏ thành các phần có ngữ nghĩa hoàn chỉnh dựa trên ngữ cảnh tổng thể.

Dưới đây là BẢN TÓM TẮT tổng thể của tài liệu để bạn nắm được cấu trúc và chủ đề chính:
<summary>
{summary}
</summary>

<instructions>
1. Văn bản chi tiết bên dưới đã được chia ranh giới tạm thời, đánh dấu bằng <|start_chunk_X|> và <|end_chunk_X|>.
2. Dựa vào bối cảnh từ bản tóm tắt, hãy xác định các điểm cần CẮT (split) sao cho các đoạn liên tiếp có cùng chủ đề/khoản/mục được gộp chung vào một khối.
3. Độ dài lý tưởng của mỗi khối sau khi gộp là từ 200 đến 1000 từ.
4. Nếu đoạn 1 và 2 nói về cùng một chủ đề, nhưng đoạn 3 chuyển sang chủ đề khác (dựa theo mạch tóm tắt), hãy đề xuất cắt sau đoạn 2.
5. Cung cấp câu trả lời duy nhất theo định dạng chuẩn: 'split_after: 3, 5, 8' (liệt kê tăng dần).
</instructions>

Đây là nội dung chi tiết cần phân mảnh:
<document>
{chunked_text}
</document>

Chỉ trả lời bằng chuỗi chứa ID của các đoạn cần cắt. KHÔNG giải thích gì thêm.
BẠN BẮT BUỘC PHẢI TRẢ LỜI VỚI ÍT NHẤT MỘT ĐIỂM TÁCH.
""".strip()
