SUMMARY_SYSTEM_PROMPT = """
Hãy tóm tắt ngắn gọn tài liệu sau đây trong khoảng 300-500 từ.
Tập trung vào mục đích chính, cơ quan ban hành và các chủ đề then chốt được đề cập.
Bản tóm tắt này sẽ được sử dụng làm ngữ cảnh (context) chung cho các đoạn cắt nhỏ (chunks) của tài liệu.

<document>
{document}
</document>

QUAN TRỌNG: Bạn BẮT BUỘC phải viết bản tóm tắt hoàn toàn bằng Tiếng Việt.
""".strip()


# CHUNKING_PROMPT = """
# You are an assistant specialized in splitting text into semantically consistent sections.

# <instructions>
# <instruction>The text has been divided into chunks, each marked with <|start_chunk_X|> and <|end_chunk_X|> tags, where X is the chunk number</instruction>
# <instruction>Identify points where splits should occur, such that consecutive chunks of similar themes stay together</instruction>
# <instruction>Each chunk must be between 200 and 1000 words</instruction>
# <instruction>If chunks 1 and 2 belong together but chunk 3 starts a new topic, suggest a split after chunk 2</instruction>
# <instruction>The chunks must be listed in ascending order</instruction>
# <instruction>Provide your response in the form: 'split_after: 3, 5'</instruction>
# </instructions>

# This is the document text:
# <document>
# {document_text}
# </document>

# Respond only with the IDs of the chunks where you believe a split should occur.
# YOU MUST RESPOND WITH AT LEAST ONE SPLIT.
# """.strip()

CHUNKING_PROMPT = """
Bạn là một trợ lý chuyên phân chia văn bản thành các phần có ngữ nghĩa nhất quán.

<instructions>
<instruction>Văn bản đã được chia thành các đoạn nhỏ (chunks), mỗi đoạn được đánh dấu bằng các thẻ <|start_chunk_X|> và <|end_chunk_X|>, trong đó X là số thứ tự của đoạn</instruction>
<instruction>Xác định các điểm cần tách, sao cho các đoạn liên tiếp có cùng chủ đề được gom lại với nhau</instruction>
<instruction>Mỗi đoạn phải dài từ 200 đến 1000 từ</instruction>
<instruction>Nếu đoạn 1 và 2 cùng một chủ đề nhưng đoạn 3 bắt đầu một chủ đề mới, hãy đề xuất điểm tách sau đoạn 2</instruction>
<instruction>Các đoạn phải được liệt kê theo thứ tự tăng dần</instruction>
<instruction>Cung cấp câu trả lời của bạn theo định dạng: 'split_after: 3, 5'</instruction>
</instructions>

Đây là nội dung tài liệu:
<document>
{document_text}
</document>

Chỉ trả lời bằng ID của các đoạn mà bạn cho rằng nên thực hiện việc tách.
BẠN BẮT BUỘC PHẢI TRẢ LỜI VỚI ÍT NHẤT MỘT ĐIỂM TÁCH.
""".strip()


# CONTEXTUALIZER_PROMPT = """
# You are an assistant specialized in analyzing document chunks and providing relevant context.

# <instructions>
# <instruction>You will be given a document and a specific chunk from that document</instruction>
# <instruction>Provide 2-3 concise sentences that situate this chunk within the broader document</instruction>
# <instruction>Identify the main topic or concept discussed in the chunk</instruction>
# <instruction>Include relevant information or comparisons from the broader document context</instruction>
# <instruction>Note how this information relates to the overall theme or purpose of the document if applicable</instruction>
# <instruction>Include key figures, dates, or percentages that provide important context</instruction>
# <instruction>Avoid phrases like "This chunk discusses" - instead, directly state the context</instruction>
# <instruction>Keep your response brief and focused on improving search retrieval</instruction>
# </instructions>

# Here is the document:
# <document>
# {document}
# </document>

# Here is the chunk to contextualize:
# <chunk>
# {chunk}
# </chunk>

# Respond only with the succinct context for this chunk. Do not mention it is a chunk or that you are providing context.
# """.strip()

CONTEXTUALIZER_PROMPT = """
Bạn là một trợ lý chuyên phân tích các đoạn văn bản (chunks) và cung cấp ngữ cảnh phù hợp.

<instructions>
<instruction>Bạn sẽ nhận được một tài liệu và một đoạn cắt cụ thể từ tài liệu đó</instruction>
<instruction>Hãy cung cấp 2-3 câu ngắn gọn để đặt đoạn này vào ngữ cảnh chung của toàn bộ tài liệu</instruction>
<instruction>Xác định chủ đề hoặc khái niệm chính được thảo luận trong đoạn</instruction>
<instruction>Bao gồm các thông tin hoặc sự so sánh có liên quan từ ngữ cảnh của toàn bộ tài liệu</instruction>
<instruction>Lưu ý cách thông tin này liên quan đến chủ đề hoặc mục đích tổng thể của tài liệu nếu có</instruction>
<instruction>Bao gồm các số liệu, ngày tháng hoặc tỷ lệ phần trăm quan trọng để cung cấp ngữ cảnh cần thiết</instruction>
<instruction>Tránh các cụm từ như "Đoạn này thảo luận về" - thay vào đó, hãy nêu trực tiếp ngữ cảnh</instruction>
<instruction>Giữ cho câu trả lời của bạn ngắn gọn và tập trung vào việc cải thiện khả năng tìm kiếm (search retrieval)</instruction>
</instructions>

Đây là tài liệu:
<document>
{document}
</document>

Đây là đoạn cần cung cấp ngữ cảnh:
<chunk>
{chunk}
</chunk>

Chỉ trả lời bằng ngữ cảnh súc tích cho đoạn này. Không đề cập đến việc nó là một đoạn cắt (chunk) hoặc việc bạn đang cung cấp ngữ cảnh.
""".strip()
