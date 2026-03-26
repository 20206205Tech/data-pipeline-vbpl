# import time
# from pinecone import Pinecone, ServerlessSpec
# import env

# pc = Pinecone(api_key=env.PINECONE_API_KEY)
# index_name = env.PINECONE_INDEX_NAME

# if not pc.has_index(index_name):
#     print(f"Đang tạo Index mới: {index_name}...")
#     pc.create_index(
#         name=index_name,
#         dimension=768, # Chiều vector của keepitreal/vietnamese-sbert
#         metric="cosine",
#         spec=ServerlessSpec(
#             cloud="aws",
#             region="us-east-1" # Đổi lại region tương ứng với tài khoản Pinecone của bạn
#         )
#     )

#     # Đợi index khởi tạo hoàn tất
#     while not pc.describe_index(index_name).status['ready']:
#         time.sleep(1)

#     print("✅ Đã tạo Index thành công!")
# else:
#     print(f"Index '{index_name}' đã tồn tại.")
