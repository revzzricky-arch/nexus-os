"""
Evaluation Service - Scaffold Placeholder
"""


class EvaluationService:
    async def evaluate_task(self, task_id: str):
        return {
            "task_id": task_id,
            "score": 0.0,
            "status": "scaffold - no real evaluation yet",
        }


evaluation_service = EvaluationService()
