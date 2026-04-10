SUMMARY_PROMPT = """
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
