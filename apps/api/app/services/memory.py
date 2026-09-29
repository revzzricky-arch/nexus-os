"""
Memory Service - Scaffold Placeholder
No real memory yet
"""


class MemoryService:
    async def search(self, mission_id: str, query: str, scope: str = "mission"):
        return {
            "mission_id": mission_id,
            "query": query,
            "scope": scope,
            "results": [],
            "status": "scaffold - no real memory yet",
        }

    async def create_entry(self, mission_id: str, content: str, scope: str = "mission"):
        return {"id": "scaffold-id", "mission_id": mission_id, "content": content, "scope": scope}


memory_service = MemoryService()
