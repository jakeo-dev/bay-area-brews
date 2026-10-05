from fastapi import APIRouter, Depends, status
import json
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
    number_of_potions: int
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
        inventory_rows = connection.execute(sqlalchemy.text("""
            SELECT resource_key, COALESCE(SUM(amount), 0) AS balance
            FROM ledger_entries
            WHERE resource_type = 'inventory'
            GROUP BY resource_key 
        """)).all()
        inventory = {row.resource_key: row.balance for row in inventory_rows}

        total_potions = connection.execute(sqlalchemy.text("""
                SELECT COALESCE(SUM(amount), 0) AS total
                FROM ledger_entries
                WHERE resource_type = 'potion'
            """)).scalar_one()

    return InventoryAudit(
        number_of_potions=total_potions,
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
    with db.engine.begin() as connection:
        total_ml = connection.execute(sqlalchemy.text("""
            SELECT COALESCE(SUM(amount), 0)
            FROM ledger_entries
            WHERE resource_type = 'inventory' AND (resource_key = 'red_ml' OR resource_key = 'green_ml' OR resource_key = 'blue_ml' OR resource_key = 'dark_ml')
        """)).scalar_one()

        total_gold = connection.execute(sqlalchemy.text("""
            SELECT COALESCE(SUM(amount), 0) AS balance
            FROM ledger_entries
            WHERE resource_type = 'inventory' AND resource_key = 'gold'
        """)).scalar_one()

        additional_ml_capacity = connection.execute(sqlalchemy.text("""
            SELECT COALESCE(SUM(amount), 0)
            FROM ledger_entries
            WHERE resource_type = 'capacity' AND resource_key = 'ml'
        """)).scalar_one()

    current_ml_limit = (1 + additional_ml_capacity) * 10000
    new_ml_capacity = int(total_ml * 10 > current_ml_limit * 9 and total_gold >= 1500)

    return CapacityPlan(potion_capacity=0, ml_capacity=new_ml_capacity)


@router.post("/deliver/{order_id}", status_code=status.HTTP_204_NO_CONTENT)
def deliver_capacity_plan(capacity_purchase: CapacityPlan, order_id: int):
    """
    Processes the delivery of the planned capacity purchase. order_id is a
    unique value representing a single delivery; the call is idempotent.

    - Start with 1 capacity for 50 potions and 1 capacity for 10,000 ml of potion.
    - Each additional capacity unit costs 1000 gold.
    """
    print(f"capacity delivered: {capacity_purchase} order_id: {order_id}")

    total_units = capacity_purchase.potion_capacity + capacity_purchase.ml_capacity
    total_cost = total_units * 1000

    with db.engine.begin() as connection:
        transaction_id = connection.execute(
            sqlalchemy.text("""
                INSERT INTO transactions (request_type, request_id, response)
                VALUES (:request_type, :request_id, CAST(:response AS jsonb))
                RETURNING id
            """),
            {
                "request_type": "capacity_delivery",
                "request_id": order_id,
                "response": json.dumps(capacity_purchase.model_dump()),
            },
        ).scalar_one()

        entries = [
            ("capacity", "potion", capacity_purchase.potion_capacity),
            ("capacity", "ml", capacity_purchase.ml_capacity),
            ("inventory", "gold", -total_cost),
        ]
        connection.execute(
            sqlalchemy.text("""
                INSERT INTO ledger_entries
                    (transaction_id, resource_type, resource_key, amount)
                VALUES (:transaction_id, :resource_type, :resource_key, :amount)
            """),
            [
                {
                    "transaction_id": transaction_id,
                    "resource_type": resource_type,
                    "resource_key": resource_key,
                    "amount": amount,
                }
                for resource_type, resource_key, amount in entries
                if amount != 0
            ],
        )

    return status.HTTP_204_NO_CONTENT
