"""
RAG Service - Scaffold Placeholder
Local-first embedding, replaceable (D2)
No real RAG pipeline yet
"""


class RAGService:
    async def query(self, collection_id: str, query: str, top_k: int = 5):
        return {
            "collection_id": collection_id,
            "query": query,
            "results": [],
            "status": "scaffold - no real RAG yet, local-first provider planned",
        }

    async def ingest_document(self, collection_id: str, filename: str):
        return {
            "collection_id": collection_id,
            "filename": filename,
            "status": "scaffold - no real ingestion yet",
        }


rag_service = RAGService()
