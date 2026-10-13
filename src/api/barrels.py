from dataclasses import dataclass
from decimal import Decimal
import json
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
    delivered_response = json.dumps(
        [barrel.model_dump() for barrel in barrels_delivered]
    )

    with db.engine.begin() as connection:
        transaction_id = connection.execute(
            sqlalchemy.text("""
            INSERT INTO transactions (request_type, request_id, response)
            VALUES (:request_type, :request_id, CAST(:response AS jsonb))
            RETURNING id
        """),
            {
                "request_type": "barrel_delivery",
                "request_id": order_id,
                "response": delivered_response,
            },
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

    expanded_wholesale_catalog = []
    for barrel in wholesale_catalog:
        expanded_wholesale_catalog.append(barrel)
        if barrel.quantity > 1:
            for i in range(barrel.quantity // 2):
                expanded_wholesale_catalog.append(barrel)

    # filter by prices less than current gold
    filtered_wholesale_catalog = [
        barrel
        for barrel in expanded_wholesale_catalog
        if barrel.price <= gold
        and any(amount > 0 for amount in barrel.potion_type)
        and "JUNK" not in barrel.sku
        and "MINI" not in barrel.sku
        and barrel.potion_type[0] > 0
    ]
    print(f"filtered_wholesale_catalog: {filtered_wholesale_catalog}")

    # shuffle potential barrels
    shuffled_wholesale_catalog = list(filtered_wholesale_catalog)
    random.shuffle(shuffled_wholesale_catalog)

    # prioritize dark barrels, then red, unstocked liquid, and price per ml.
    sorted_wholesale_catalog = sorted(
        shuffled_wholesale_catalog,
        key=lambda barrel: (
            not barrel.potion_type[3] > 0,
            not barrel.potion_type[0] > 0,
            any(
                current_liquids[index] > 0
                for index, amount in enumerate(barrel.potion_type)
                if amount > 0
            ),
            barrel.price / barrel.ml_per_barrel,
        ),
    )
    print(f"sorted_wholesale_catalog: {sorted_wholesale_catalog} ")

    current_plan = []
    current_plan_cost = 0
    current_plan_ml = sum(current_liquids)
    current_green_blue_ml = current_liquids[1] + current_liquids[2]
    barrel_budget = gold // 999999999999  # dont buy barrels anymore

    def fits_ml_limits(barrel: Barrel) -> bool:
        barrel_ml = Decimal(barrel.ml_per_barrel)
        green_blue_ml = barrel_ml * Decimal(str(sum(barrel.potion_type[1:3])))
        projected_total_ml = current_plan_ml + barrel_ml
        projected_green_blue_ml = current_green_blue_ml + green_blue_ml
        return (
            projected_total_ml <= max_barrel_capacity
            # make sure green-blue ml is limited to half of all ml if this barrel has green/blue
            and (
                projected_green_blue_ml * 2 <= projected_total_ml
                if barrel.potion_type[0] <= 0.5
                else True
            )
            # ONLY get barrels with some amount of red ml
            and barrel.potion_type[0] > 0.2
        )

    """
    # Only choose a red-containing barrel in the first selection pass.
    selected_skus = set()
    components = [0]
    for component in components:
        component_barrels = [
            barrel
            for barrel in sorted_wholesale_catalog
            if barrel.sku not in selected_skus
            and barrel.potion_type[component] > 0
            and (
                component == 3
                or not any(
                    current_liquids[index] > 0
                    for index, amount in enumerate(barrel.potion_type)
                    if amount > 0
                )
            )
        ]
        for barrel in component_barrels:
            if current_plan_cost + barrel.price <= barrel_budget and fits_ml_limits(
                barrel
            ):
                print(f"A barrel in plan: {barrel.sku}")
                current_plan.append(BarrelOrder(sku=barrel.sku, quantity=1))
                current_plan_cost += barrel.price
                current_plan_ml += Decimal(barrel.ml_per_barrel)
                current_green_blue_ml += Decimal(barrel.ml_per_barrel) * Decimal(
                    str(sum(barrel.potion_type[1:3]))
                )
                selected_skus.add(barrel.sku)
                break
    """

    # spend remaining gold on barrels with best cost/ml
    for barrel in sorted_wholesale_catalog:
        print(
            f"Checking {barrel.sku}: Cost={barrel.price} (Budget: {barrel_budget}), Fits ML={fits_ml_limits(barrel)}"
        )
        if current_plan_cost + barrel.price <= barrel_budget and fits_ml_limits(barrel):
            print(f"barrel in plan: {barrel.sku}")
            existing_order = next(
                (order for order in current_plan if order.sku == barrel.sku),
                None,
            )
            if existing_order is not None:
                existing_order.quantity += 1
            else:
                current_plan.append(BarrelOrder(sku=barrel.sku, quantity=1))

            current_plan_cost += barrel.price
            current_plan_ml += Decimal(barrel.ml_per_barrel)
            current_green_blue_ml += Decimal(barrel.ml_per_barrel) * Decimal(
                str(sum(barrel.potion_type[1:3]))
            )

    print(f"final barrel plan: {current_plan}")
    print(f"final plan cost: {current_plan_cost}")
    print(f"final plan ml: {current_plan_ml}")

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

        capacity_rows = connection.execute(sqlalchemy.text("""
            SELECT resource_key, COALESCE(SUM(amount), 0) AS sum
            FROM ledger_entries
            WHERE resource_type = 'capacity'
            GROUP BY resource_key
        """)).all()
        capacity = {row.resource_key: row.sum for row in capacity_rows}

    return create_barrel_plan(
        gold=inventory.get("gold", 0),
        max_barrel_capacity=(capacity.get("ml", 0) + 1) * 10000,
        current_liquids=[
            inventory.get("red_ml", 0),
            inventory.get("green_ml", 0),
            inventory.get("blue_ml", 0),
            inventory.get("dark_ml", 0),
        ],
        target_component=target_component,
        wholesale_catalog=wholesale_catalog,
    )
