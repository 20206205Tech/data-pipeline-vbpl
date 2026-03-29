import torch
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_pinecone import PineconeVectorStore
from pinecone import Pinecone

import env

if torch.cuda.is_available():
    current_device = "cuda"
elif torch.backends.mps.is_available():
    current_device = "mps"
else:
    current_device = "cpu"


embeddings_model = HuggingFaceEmbeddings(
    model_name="keepitreal/vietnamese-sbert",
    model_kwargs={"device": current_device},
    encode_kwargs={"normalize_embeddings": True},
)


pc = Pinecone(api_key=env.PINECONE_API_KEY)
pinecone_index = pc.Index(env.PINECONE_INDEX_NAME)


vectorstore = PineconeVectorStore(
    index=pinecone_index, embedding=embeddings_model, text_key="text"
)
