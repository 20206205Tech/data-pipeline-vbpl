import torch
from langchain_huggingface import HuggingFaceEmbeddings

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
