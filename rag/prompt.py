SUMMARY_SYSTEM_PROMPT = """
Bạn là một chuyên gia phân tích dữ liệu văn bản. Hãy tóm tắt tài liệu sau đây trong khoảng 300-500 từ.

<objectives>
1. Xác định rõ loại văn bản, cơ quan ban hành và mục đích cốt lõi của tài liệu.
2. Tóm tắt các chủ đề, chính sách, hoặc quy định then chốt nhất.
3. Nêu bật các đối tượng chịu tác động chính hoặc các mốc thời gian/số liệu quan trọng.
</objectives>

Bản tóm tắt này sẽ được sử dụng làm "Bức tranh toàn cảnh" (Global Context) để hỗ trợ AI phân mảnh (chunking) và định tuyến tìm kiếm trong hệ thống RAG.

<document>
{document}
</document>

QUAN TRỌNG: Bạn BẮT BUỘC phải viết bản tóm tắt hoàn toàn bằng Tiếng Việt, sử dụng văn phong trang trọng, khách quan và súc tích.
""".strip()


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


CONTEXTUALIZER_PROMPT = """
Bạn là một chuyên gia xử lý dữ liệu cho hệ thống tìm kiếm Vector (RAG).
Nhiệm vụ của bạn là sinh ra phần "Ngữ cảnh dẫn nhập" (Context) cho một đoạn trích ngắn, giúp đoạn trích này đứng độc lập mà vẫn trọn vẹn ý nghĩa khi tìm kiếm.

<instructions>
1. Bạn sẽ nhận được BẢN TÓM TẮT của tài liệu gốc và MỘT ĐOẠN TRÍCH (chunk) từ tài liệu đó.
2. Hãy viết 2-3 câu ngắn gọn để "neo" đoạn trích này vào bối cảnh chung.
3. Giải quyết các đại từ hoặc tham chiếu mơ hồ (ví dụ: "Nghị định này", "Khoản 2" -> phải làm rõ là của văn bản nào, nói về cái gì dựa vào tóm tắt).
4. Bổ sung các thực thể quan trọng (tên văn bản, cơ quan ban hành, chủ đề) từ tóm tắt nếu đoạn trích bị thiếu.
5. KHÔNG dùng các cụm từ thừa như "Đoạn này thảo luận về", "Dựa theo tóm tắt". Hãy đi thẳng vào thông tin.
</instructions>

Đây là bản tóm tắt của tài liệu gốc:
<summary>
{summary}
</summary>

Đây là đoạn trích cần bổ sung ngữ cảnh:
<chunk>
{chunk}
</chunk>

Chỉ trả lời bằng phần ngữ cảnh súc tích. Tuyệt đối không nhắc lại nội dung của đoạn trích.
""".strip()
