from dataclasses import dataclass
import random
from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field, field_validator
from typing import List

import sqlalchemy
from src.api import auth
from src import database as db

router = APIRouter(
    prefix="/barrels",
    tags=["barrels"],
    dependencies=[Depends(auth.get_api_key)],
)


class Barrel(BaseModel):
    sku: str
    ml_per_barrel: int = Field(gt=0, description="Must be greater than 0")
    potion_type: List[float] = Field(
        ...,
        min_length=4,
        max_length=4,
        description="Must contain exactly 4 elements: [r, g, b, d] that sum to 1.0",
    )
    price: int = Field(ge=0, description="Price must be non-negative")
    quantity: int = Field(ge=0, description="Quantity must be non-negative")

    @field_validator("potion_type")
    @classmethod
    def validate_potion_type(cls, potion_type: List[float]) -> List[float]:
        if len(potion_type) != 4:
            raise ValueError("potion_type must have exactly 4 elements: [r, g, b, d]")

        print(f"received potion_type={potion_type}, total={sum(potion_type)}")

        total = sum(potion_type)
        if abs(total) < 1e-6:
            return potion_type
        if abs(total - 100.0) < 1e-6:
            potion_type = [amount / 100 for amount in potion_type]
        elif not abs(total - 1.0) < 1e-6:
            raise ValueError("Sum of potion_type values must be exactly 1.0")
        return potion_type


class BarrelOrder(BaseModel):
    sku: str
    quantity: int = Field(gt=0, description="Quantity must be greater than 0")


@dataclass
class BarrelSummary:
    gold_paid: int


def calculate_barrel_summary(barrels: List[Barrel]) -> BarrelSummary:
    return BarrelSummary(gold_paid=sum(b.price * b.quantity for b in barrels))


@router.post("/deliver/{order_id}", status_code=status.HTTP_204_NO_CONTENT)
def post_deliver_barrels(barrels_delivered: List[Barrel], order_id: int):
    """
    Processes barrels delivered based on the provided order_id. order_id is a unique value representing
    a single delivery; the call is idempotent based on the order_id.
    """
    print(f"barrels delivered: {barrels_delivered} order_id: {order_id}")

    delivery = calculate_barrel_summary(barrels_delivered)

    with db.engine.begin() as connection:
        transaction_id = connection.execute(
            sqlalchemy.text("""
            INSERT INTO transactions (request_type, request_id, response)
            VALUES (:request_type, :request_id, NULL)
            RETURNING id
        """),
            {"request_type": "barrel_delivery", "request_id": order_id},
        ).scalar_one()

        liquid_columns = ("red_ml", "green_ml", "blue_ml", "dark_ml")
        liquid_totals = {
            column: sum(
                int(barrel.ml_per_barrel * barrel.quantity * barrel.potion_type[index])
                for barrel in barrels_delivered
            )
            for index, column in enumerate(liquid_columns)
        }
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
                for resource_type, resource_key, amount in [
                    ("inventory", "gold", -delivery.gold_paid),
                    *[
                        ("inventory", column, liquid_totals[column])
                        for column in liquid_columns
                    ],
                ]
                if amount != 0
            ],
        )

    pass


def create_barrel_plan(
    gold: int,
    max_barrel_capacity: int,
    current_liquids: List[int],
    target_component: int,
    wholesale_catalog: List[Barrel],
) -> List[BarrelOrder]:
    print(
        f"gold: {gold}, max_barrel_capacity: {max_barrel_capacity}, current_liquids: {current_liquids}, wholesale_catalog: {wholesale_catalog}"
    )

    # filter by prices less than current gold
    filtered_wholesale_catalog = [
        barrel
        for barrel in wholesale_catalog
        if barrel.price <= gold and any(amount > 0 for amount in barrel.potion_type)
    ]
    # sort by price per ml, lowest to highest
    shuffled_wholesale_catalog = list(filtered_wholesale_catalog)
    random.shuffle(shuffled_wholesale_catalog)
    sorted_wholesale_catalog = sorted(
        shuffled_wholesale_catalog,
        key=lambda barrel: barrel.price / barrel.ml_per_barrel,
    )

    # return an empty list if no good barrels found
    current_plan = []

    current_plan_cost = 0
    i = 0
    while (
        i < len(sorted_wholesale_catalog)
        and current_plan_cost + sorted_wholesale_catalog[i].price <= gold
    ):
        barrel = sorted_wholesale_catalog[i]
        current_plan.append(BarrelOrder(sku=barrel.sku, quantity=1))
        current_plan_cost += barrel.price
        i += 1

    # try to get dark barrel if its in the catalog now
    """ if current_liquids[target_component] < 1000:
        barrel = min(
            (
                barrel
                for barrel in sorted_wholesale_catalog
                if barrel.potion_type[3] == 1
            ),
            key=lambda barrel: barrel.ml_per_barrel,
            default=None,
        )
        if barrel and barrel.price <= gold:
            current_plan.append(BarrelOrder(sku=barrel.sku, quantity=1))

    if current_liquids[target_component] < 1000:
        barrel = min(
            (
                barrel
                for barrel in sorted_wholesale_catalog
                if barrel.potion_type[target_component] == 1 and "SMALL" in barrel.sku
            ),
            key=lambda barrel: barrel.ml_per_barrel,
            default=None,
        )
        if barrel and barrel.price <= gold:
            current_plan.append(BarrelOrder(sku=barrel.sku, quantity=1)) """

    return current_plan


@router.post("/plan", response_model=List[BarrelOrder])
def get_wholesale_purchase_plan(wholesale_catalog: List[Barrel]):
    """
    Gets the plan for purchasing wholesale barrels. The call passes in a catalog of available barrels
    and the shop returns back which barrels they'd like to purchase and how many.
    """
    print(f"barrel catalog: {wholesale_catalog}")

    # randomly choose red (0), green (1), blue (2)
    target_component = random.randint(0, 2)

    with db.engine.begin() as connection:
        inventory_rows = connection.execute(sqlalchemy.text("""
            SELECT resource_key, COALESCE(SUM(amount), 0) AS sum
            FROM ledger_entries
            WHERE resource_type = 'inventory'
            GROUP BY resource_key
        """)).all()
        inventory = {row.resource_key: row.sum for row in inventory_rows}

    return create_barrel_plan(
        gold=inventory.get("gold", 0),
        max_barrel_capacity=10000,
        current_liquids=[
            inventory.get("red_ml", 0),
            inventory.get("green_ml", 0),
            inventory.get("blue_ml", 0),
            inventory.get("dark_ml", 0),
        ],
        target_component=target_component,
        wholesale_catalog=wholesale_catalog,
    )
