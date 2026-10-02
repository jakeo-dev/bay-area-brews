from fastapi import APIRouter, Depends, status
from pydantic import BaseModel
from src.api import auth
from src import database as db
import sqlalchemy

router = APIRouter(
    prefix="/info",
    tags=["info"],
    dependencies=[Depends(auth.get_api_key)],
)


class Timestamp(BaseModel):
    day: str
    hour: int


@router.post("/current_time", status_code=status.HTTP_204_NO_CONTENT)
def post_time(timestamp: Timestamp):
    """
    Shares what the latest time (in game time) is.
    """
    with db.engine.begin() as connection:
        connection.execute(
            sqlalchemy.text("""
                UPDATE game_time
                SET day = :day, hour = :hour
                WHERE id = 1
            """),
            timestamp.model_dump(),
        )
    return timestamp.day, timestamp.hour
