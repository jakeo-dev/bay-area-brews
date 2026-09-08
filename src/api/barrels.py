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
        if not abs(sum(potion_type) - 1.0) < 1e-6:
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
        connection.execute(
            sqlalchemy.text("""
                UPDATE global_inventory 
                SET gold = gold - :gold_paid
                """),
            [{"gold_paid": delivery.gold_paid}],
        )

        liquid_columns = ("red_ml", "green_ml", "blue_ml", "dark_ml")
        liquid_totals = {
            column: sum(
                int(barrel.ml_per_barrel * barrel.quantity * barrel.potion_type[index])
                for barrel in barrels_delivered
            )
            for index, column in enumerate(liquid_columns)
        }
        updates = ", ".join(
            f"{column} = {column} + :{column}" for column in liquid_columns
        )
        connection.execute(
            sqlalchemy.text(f"UPDATE global_inventory SET {updates}"), liquid_totals
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

    if current_liquids[target_component] < 1000:
        barrel = min(
            (
                barrel
                for barrel in wholesale_catalog
                if barrel.potion_type[target_component] == 1 and "SMALL" in barrel.sku
            ),
            key=lambda barrel: barrel.ml_per_barrel,
            default=None,
        )
        if barrel and barrel.price <= gold:
            return [BarrelOrder(sku=barrel.sku, quantity=1)]

    # return an empty list if no affordable red barrel is found
    return []


@router.post("/plan", response_model=List[BarrelOrder])
def get_wholesale_purchase_plan(wholesale_catalog: List[Barrel]):
    """
    Gets the plan for purchasing wholesale barrels. The call passes in a catalog of available barrels
    and the shop returns back which barrels they'd like to purchase and how many.
    """
    print(f"barrel catalog: {wholesale_catalog}")

    target_component = random.randint(0, 3)

    with db.engine.begin() as connection:
        row = connection.execute(sqlalchemy.text("""
                SELECT gold, red_ml, green_ml, blue_ml, dark_ml
                FROM global_inventory
                """)).one()

    return create_barrel_plan(
        gold=row.gold,
        max_barrel_capacity=10000,
        current_liquids=[row.red_ml, row.green_ml, row.blue_ml, row.dark_ml],
        target_component=target_component,
        wholesale_catalog=wholesale_catalog,
    )
