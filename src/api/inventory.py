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
        potion_rows = connection.execute(sqlalchemy.text("""
            SELECT id, name
            FROM potion_mixtures
        """)).all()
        inventory_rows = connection.execute(sqlalchemy.text("""
            SELECT resource_key, COALESCE(SUM(amount), 0) AS balance
            FROM ledger_entries
            WHERE resource_type = 'inventory'
            GROUP BY resource_key 
        """)).all()
        inventory = {row.resource_key: row.balance for row in inventory_rows}

        potion_numbers = {}

        for row in potion_rows:
            thing = connection.execute(
                sqlalchemy.text("""
                    SELECT COALESCE(SUM(amount), 0) AS balance
                    FROM ledger_entries
                    WHERE resource_type = 'potion' AND resource_key = :resource_key
                """),
                {"resource_key": f"potion:{row.id}"},
            ).scalar_one()
            potion_numbers[row.name] = thing

    return InventoryAudit(
        lemonade_number=potion_numbers.get("Lemonade", 0),
        water_number=potion_numbers.get("Water", 0),
        cappuccino_number=potion_numbers.get("Cappuccino", 0),
        hot_chocolate_number=potion_numbers.get("Hot chocolate", 0),
        grape_juice_number=potion_numbers.get("Grape juice", 0),
        red_potion_number=potion_numbers.get("Red potion", 0),
        green_potion_number=potion_numbers.get("Green potion", 0),
        blue_potion_number=potion_numbers.get("Blue potion", 0),
        dark_potion_number=potion_numbers.get("Dark potion", 0),
        ml_in_barrels=inventory.get("red_ml", 0)
        + inventory.get("green_ml", 0)
        + inventory.get("blue_ml", 0)
        + inventory.get("dark_ml", 0),
        gold=inventory.get("gold", 0),
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
