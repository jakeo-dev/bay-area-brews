import random

from fastapi import APIRouter
from pydantic import BaseModel, Field
from typing import List, Annotated, Sequence

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


def create_catalog(rows: Sequence[sqlalchemy.Row]) -> List[CatalogItem]:
    full_catalog = [
        CatalogItem(
            sku=row.sku,
            name=row.name,
            quantity=row.number,
            price=row.price,
            potion_type=[
                row.red_amount,
                row.green_amount,
                row.blue_amount,
                row.dark_amount,
            ],
        )
        for row in rows
        if row.number > 0
    ]
    random.shuffle(full_catalog)
    full_catalog.sort(key=lambda item: -item.potion_type[0])

    filtered_catalog = full_catalog[:6]
    return filtered_catalog


@router.get("/catalog/", tags=["catalog"], response_model=List[CatalogItem])
def get_catalog() -> List[CatalogItem]:
    """
    Retrieves the catalog of items. Each unique item combination should have only a single price.
    You can have at most 6 potion SKUs offered in your catalog at one time.
    """
    with db.engine.begin() as connection:
        rows = connection.execute(sqlalchemy.text("""
            SELECT potion_mixtures.sku, potion_mixtures.name, COALESCE(SUM(ledger_entries.amount), 0) AS number, potion_mixtures.price, potion_mixtures.red_amount, potion_mixtures.green_amount, potion_mixtures.blue_amount, potion_mixtures.dark_amount
            FROM potion_mixtures
            LEFT JOIN ledger_entries ON ledger_entries.resource_type = 'potion' AND ledger_entries.resource_key = potion_mixtures.sku
            GROUP BY potion_mixtures.id
            ORDER BY potion_mixtures.id
        """)).all()

    return create_catalog(rows)
