from fastapi import APIRouter

# Б1 добавляет маршруты из contracts/openapi.json в этот роутер.
router = APIRouter(tags=["Competitions"])
