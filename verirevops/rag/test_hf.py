import os
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
os.environ["HF_HOME"] = "/app/data/hf_cache"
from llama_index.postprocessor.sbert_rerank import SentenceTransformerRerank
reranker = SentenceTransformerRerank(top_n=2, model="BAAI/bge-reranker-base")
