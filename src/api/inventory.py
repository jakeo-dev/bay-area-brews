from typing import Any, Sequence

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field
import sqlalchemy
from src.api import auth
from src import database as db

router = APIRouter(
    prefix="/inventory",
    tags=["inventory"],
    dependencies=[Depends(auth.get_api_key)],
)


class InventoryAudit(BaseModel):
    thing: Sequence[sqlalchemy.Row[Any]]
    lemonade_number: int
    water_number: int
    cappuccino_number: int
    hot_chocolate_number: int
    grape_juice_number: int
    red_potion_number: int
    green_potion_number: int
    blue_potion_number: int
    dark_potion_number: int
    ml_in_barrels: int
    gold: int


class CapacityPlan(BaseModel):
    potion_capacity: int = Field(
        ge=0, le=10, description="Potion capacity units, max 10"
    )
    ml_capacity: int = Field(ge=0, le=10, description="ML capacity units, max 10")


@router.get("/audit", response_model=InventoryAudit)
def get_inventory():
    """
    Returns an audit of the current inventory. Any discrepancies between
    what is reported here and my source of truth will be posted
    as errors on potion exchange.
    """

    with db.engine.begin() as connection:
        inventory = connection.execute(sqlalchemy.text("""
            SELECT gold, red_ml, green_ml, blue_ml, dark_ml
            FROM global_inventory
            """)).one()
        potion_rows = connection.execute(sqlalchemy.text("""
            SELECT name, number
            FROM potion_mixtures
            """)).all()

    potion_numbers = {row.name: row.number for row in potion_rows}

    return InventoryAudit(
        thing=potion_rows,
        lemonade_number=potion_numbers.get("lemonade", 0),
        water_number=potion_numbers.get("water", 0),
        cappuccino_number=potion_numbers.get("cappuccino", 0),
        hot_chocolate_number=potion_numbers.get("hot_chocolate", 0),
        grape_juice_number=potion_numbers.get("grape_juice", 0),
        red_potion_number=potion_numbers.get("red_potion", 0),
        green_potion_number=potion_numbers.get("green_potion", 0),
        blue_potion_number=potion_numbers.get("blue_potion", 0),
        dark_potion_number=potion_numbers.get("dark_potion", 0),
        ml_in_barrels=inventory.red_ml
        + inventory.green_ml
        + inventory.blue_ml
        + inventory.dark_ml,
        gold=inventory.gold,
    )


@router.post("/plan", response_model=CapacityPlan)
def get_capacity_plan():
    """
    Provides a daily capacity purchase plan.

    - Start with 1 capacity for 50 potions and 1 capacity for 10,000 ml of potion.
    - Each additional capacity unit costs 1000 gold.
    """
    return CapacityPlan(potion_capacity=0, ml_capacity=0)


@router.post("/deliver/{order_id}", status_code=status.HTTP_204_NO_CONTENT)
def deliver_capacity_plan(capacity_purchase: CapacityPlan, order_id: int):
    """
    Processes the delivery of the planned capacity purchase. order_id is a
    unique value representing a single delivery; the call is idempotent.

    - Start with 1 capacity for 50 potions and 1 capacity for 10,000 ml of potion.
    - Each additional capacity unit costs 1000 gold.
    """
    print(f"capacity delivered: {capacity_purchase} order_id: {order_id}")
    pass
