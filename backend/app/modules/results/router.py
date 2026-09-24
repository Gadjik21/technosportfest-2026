from fastapi import APIRouter

# Б2 добавляет маршруты результатов и рейтинга из contracts/openapi.json.
router = APIRouter(tags=["Results", "Rating"])
