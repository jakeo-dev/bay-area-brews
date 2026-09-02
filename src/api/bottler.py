from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field, field_validator
from typing import List

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

    red_potions_delivered = 0
    green_potions_delivered = 0
    blue_potions_delivered = 0

    for potion in potions_delivered:
        if potion.potion_type == [100, 0, 0, 0]:
            red_potions_delivered += potion.quantity
        if potion.potion_type == [0, 100, 0, 0]:
            green_potions_delivered += potion.quantity
        if potion.potion_type == [0, 0, 100, 0]:
            blue_potions_delivered += potion.quantity

    with db.engine.begin() as connection:
        connection.execute(
            sqlalchemy.text("""
                    UPDATE global_inventory
                    SET red_potions = red_potions + :red_potions
                    SET green_potions = green_potions + :green_potions
                    SET blue_potions = blue_potions + :blue_potions
                    SET red_ml = red_ml - :red_ml
                    SET green_ml = green_ml - :green_ml
                    SET blue_ml = blue_ml - :blue_ml
                    """),
            {
                "red_potions": red_potions_delivered,
                "green_potions": green_potions_delivered,
                "blue_potions": blue_potions_delivered,
                "red_ml": red_potions_delivered * 100,
                "green_ml": green_potions_delivered * 100,
                "blue_ml": blue_potions_delivered * 100,
            },
        )


def create_bottle_plan(
    red_ml: int,
    green_ml: int,
    blue_ml: int,
    dark_ml: int,
    maximum_potion_capacity: int,
    current_potion_inventory: List[PotionMixes],
) -> List[PotionMixes]:
    potions_to_make = []

    if red_ml >= 100:
        potions_to_make.append(
            PotionMixes(
                potion_type=[100, 0, 0, 0],
                quantity=red_ml // 100,
            )
        )
    if green_ml >= 100:
        potions_to_make.append(
            PotionMixes(
                potion_type=[0, 100, 0, 0],
                quantity=green_ml // 100,
            )
        )
    if blue_ml >= 100:
        potions_to_make.append(
            PotionMixes(
                potion_type=[0, 0, 100, 0],
                quantity=blue_ml // 100,
            )
        )

    print(f"bottle plan {potions_to_make}")
    return potions_to_make


@router.post("/plan", response_model=List[PotionMixes])
def get_bottle_plan():
    """
    Gets the plan for bottling potions.
    Each bottle has a quantity of what proportion of red, green, blue, and dark potions to add.
    Colors are expressed in integers from 0 to 100 that must sum up to exactly 100.
    """

    with db.engine.begin() as connection:
        row = connection.execute(sqlalchemy.text("""
                SELECT red_ml, green_ml, blue_ml
                FROM global_inventory
                """)).one()

    red_ml = row.red_ml
    green_ml = row.green_ml
    blue_ml = row.blue_ml

    return create_bottle_plan(
        red_ml=red_ml,
        green_ml=green_ml,
        blue_ml=blue_ml,
        dark_ml=0,  # TODO: figure out dark potions
        maximum_potion_capacity=50,
        current_potion_inventory=[],
    )


if __name__ == "__main__":
    print(get_bottle_plan())
