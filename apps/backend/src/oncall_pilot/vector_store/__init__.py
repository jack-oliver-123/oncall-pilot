"""tenant-safe Milvus adapter；导入和构造均不创建 client。"""

from oncall_pilot.vector_store.store import MilvusVectorStore, VectorChunk

__all__ = ["MilvusVectorStore", "VectorChunk"]
