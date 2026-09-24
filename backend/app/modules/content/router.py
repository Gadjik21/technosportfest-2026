from fastapi import APIRouter

# Б2 добавляет маршруты новостей и документов из contracts/openapi.json.
router = APIRouter(tags=["Content"])
