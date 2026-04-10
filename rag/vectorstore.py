from langchain_pinecone import PineconeVectorStore
from pinecone import Pinecone

import env

from .embedding import embeddings_model

pc = Pinecone(api_key=env.PINECONE_API_KEY)
pinecone_index = pc.Index(env.PINECONE_INDEX_NAME)


vectorstore = PineconeVectorStore(
    index=pinecone_index, embedding=embeddings_model, text_key="text"
)
