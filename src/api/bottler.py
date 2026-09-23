from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator
from typing import List, Sequence

import sqlalchemy
from src.api import auth
from src import database as db

router = APIRouter(
    prefix="/bottler",
    tags=["bottler"],
    dependencies=[Depends(auth.get_api_key)],
)


class PotionMixes(BaseModel):
    potion_type: List[int] = Field(
        ...,
        min_length=4,
        max_length=4,
        description="Must contain exactly 4 elements: [r, g, b, d]",
    )
    quantity: int = Field(
        ..., ge=1, le=10000, description="Quantity must be between 1 and 10,000"
    )

    @field_validator("potion_type")
    @classmethod
    def validate_potion_type(cls, potion_type: List[int]) -> List[int]:
        if sum(potion_type) != 100:
            raise ValueError("Sum of potion_type values must be exactly 100")
        return potion_type


@router.post("/deliver/{order_id}", status_code=status.HTTP_204_NO_CONTENT)
def post_deliver_bottles(potions_delivered: List[PotionMixes], order_id: int):
    """
    Delivery of potions requested after plan. order_id is a unique value representing
    a single delivery; the call is idempotent based on the order_id.
    """
    print(f"potions delivered: {potions_delivered} order_id: {order_id}")

    with db.engine.begin() as connection:

        transaction_id = connection.execute(
            sqlalchemy.text("""
                INSERT INTO transactions (request_type, request_id, response)
                VALUES (:request_type, :request_id, NULL)
                RETURNING id
            """),
            {"request_type": "bottler_delivery", "request_id": order_id},
        ).scalar_one()

        entries = []
        for potion in potions_delivered:
            amounts = potion.potion_type
            mixture = connection.execute(
                sqlalchemy.text("""
                SELECT sku FROM potion_mixtures
                WHERE red_amount = :red AND green_amount = :green
                  AND blue_amount = :blue AND dark_amount = :dark
                """),
                dict(zip(("red", "green", "blue", "dark"), amounts)),
            ).one()
            entries.append(("potion", mixture.sku, potion.quantity))
            for column, amount in zip(
                ("red_ml", "green_ml", "blue_ml", "dark_ml"), amounts
            ):
                entries.append(("inventory", column, -(amount * potion.quantity)))

        inventory_rows = connection.execute(sqlalchemy.text("""
            SELECT resource_key, COALESCE(SUM(amount), 0) AS balance
            FROM ledger_entries
            WHERE resource_type = 'inventory'
            GROUP BY resource_key 
        """)).all()
        inventory = {row.resource_key: row.balance for row in inventory_rows}
        for key, amount in (
            ("red_ml", "red_ml"),
            ("green_ml", "green_ml"),
            ("blue_ml", "blue_ml"),
            ("dark_ml", "dark_ml"),
        ):
            required = sum(
                entry[2]
                for entry in entries
                if entry[0] == "inventory" and entry[1] == key
            )
            if inventory.get(amount, 0) < -required:
                raise HTTPException(
                    status_code=409, detail="Insufficient liquid inventory"
                )

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


def create_bottle_plan(
    available_liquids: Sequence[int],
    potion_mixtures: Sequence[Sequence[int]],
    maximum_potion_capacity: int,
) -> List[PotionMixes]:
    potions_to_make = []
    remaining_liquids = list(available_liquids)
    remaining_capacity = maximum_potion_capacity
    print(f"potion mixtures: {potion_mixtures}")
    for potion_type in potion_mixtures:
        print(f"potion type to bottle: {potion_type}")
        if remaining_capacity <= 0:
            break
        possible = remaining_capacity

        for available, amount in zip(remaining_liquids, potion_type):
            print(f"available: {available}")
            print(f"amount: {amount}")
            if amount:
                possible = min(possible, available // amount)
        if possible > 0:
            print(f"possible greater than 0, possible {possible}")
            potions_to_make.append(
                PotionMixes(potion_type=list(potion_type), quantity=possible)
            )
            remaining_liquids = [
                available - amount * possible
                for available, amount in zip(remaining_liquids, potion_type)
            ]
            print(f"remaining_liquids: {remaining_liquids}")
            remaining_capacity -= possible

    print(f"bottle plan: {potions_to_make}")
    return potions_to_make


@router.post("/plan", response_model=List[PotionMixes])
def get_bottle_plan():
    """
    Gets the plan for bottling potions.
    Each bottle has a quantity of what proportion of red, green, blue, and dark potions to add.
    Colors are expressed in integers from 0 to 100 that must sum up to exactly 100.
    """

    with db.engine.begin() as connection:
        inventory_rows = connection.execute(sqlalchemy.text("""
            SELECT resource_key, COALESCE(SUM(amount), 0) AS balance
            FROM ledger_entries
            WHERE resource_type = 'inventory'
            GROUP BY resource_key
        """)).all()
        inventory = {row.resource_key: row.balance for row in inventory_rows}
        mixtures = connection.execute(sqlalchemy.text("""
            SELECT sku, red_amount, green_amount, blue_amount, dark_amount
            FROM potion_mixtures
            ORDER BY id
            """)).all()

        potion_mixtures: List[List[int]] = []
        for mixture in mixtures:
            balance = connection.execute(
                sqlalchemy.text("""
                    SELECT COALESCE(SUM(amount), 0) AS balance
                    FROM ledger_entries
                    WHERE resource_type = 'potion' AND resource_key = :resource_key
                """),
                {"resource_key": mixture.sku},
            ).scalar_one()
            potion_mixtures.append(
                [
                    mixture.red_amount,
                    mixture.green_amount,
                    mixture.blue_amount,
                    mixture.dark_amount,
                ]
            )

    available_liquids = [
        inventory.get("red_ml", 0),
        inventory.get("green_ml", 0),
        inventory.get("blue_ml", 0),
        inventory.get("dark_ml", 0),
    ]
    print(f"available_liquids: {available_liquids}")
    return create_bottle_plan(
        available_liquids=available_liquids,
        maximum_potion_capacity=50,
        potion_mixtures=potion_mixtures,
    )


if __name__ == "__main__":
    print(get_bottle_plan())
