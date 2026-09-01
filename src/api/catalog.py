from fastapi import APIRouter
from pydantic import BaseModel, Field
from typing import List, Annotated

import sqlalchemy
from src import database as db

router = APIRouter()


class CatalogItem(BaseModel):
    sku: Annotated[str, Field(pattern=r"^[a-zA-Z0-9_]{1,20}$")]
    name: str
    quantity: Annotated[int, Field(ge=1, le=10000)]
    price: Annotated[int, Field(ge=1, le=500)]
    potion_type: List[int] = Field(
        ...,
        min_length=4,
        max_length=4,
        description="Must contain exactly 4 elements: [r, g, b, d]",
    )


def create_catalog(
    red_potions: int,
    green_potions: int,
    blue_potions: int,
) -> List[CatalogItem]:
    catalog = []

    if red_potions > 0:
        catalog.append(
            CatalogItem(
                sku="RED_POTION_0",
                name="red potion",
                quantity=red_potions,
                price=50,
                potion_type=[100, 0, 0, 0],
            )
        )

    if green_potions > 0:
        catalog.append(
            CatalogItem(
                sku="GREEN_POTION_0",
                name="green potion",
                quantity=green_potions,
                price=50,
                potion_type=[0, 100, 0, 0],
            )
        )

    if blue_potions > 0:
        catalog.append(
            CatalogItem(
                sku="BLUE_POTION_0",
                name="blue potion",
                quantity=blue_potions,
                price=50,
                potion_type=[0, 0, 100, 0],
            )
        )

    return catalog


@router.get("/catalog/", tags=["catalog"], response_model=List[CatalogItem])
def get_catalog() -> List[CatalogItem]:
    """
    Retrieves the catalog of items. Each unique item combination should have only a single price.
    You can have at most 6 potion SKUs offered in your catalog at one time.
    """
    with db.engine.begin() as connection:
        row = connection.execute(sqlalchemy.text("""
                    SELECT red_potions, green_potions, blue_potions
                    FROM global_inventory
                    """)).one()

    return create_catalog(
        red_potions=row.red_potions,
        green_potions=row.green_potions,
        blue_potions=row.blue_potions,
    )
