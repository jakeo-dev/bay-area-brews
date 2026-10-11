import json

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
import sqlalchemy
from src.api import auth
from enum import Enum
from typing import List, Optional
from src import database as db

router = APIRouter(
    prefix="/carts",
    tags=["cart"],
    dependencies=[Depends(auth.get_api_key)],
)


class SearchSortOptions(str, Enum):
    customer_name = "customer_name"
    item_sku = "item_sku"
    line_item_total = "line_item_total"
    timestamp = "timestamp"


class SearchSortOrder(str, Enum):
    asc = "asc"
    desc = "desc"


class LineItem(BaseModel):
    line_item_id: int
    item_sku: str
    customer_name: str
    line_item_total: int
    timestamp: str


class SearchResponse(BaseModel):
    previous: Optional[str] = None
    next: Optional[str] = None
    results: List[LineItem]


@router.get("/search/", response_model=SearchResponse, tags=["search"])
def search_orders(
    customer_name: str = "",
    potion_sku: str = "",
    search_page: str = "",
    sort_col: SearchSortOptions = SearchSortOptions.timestamp,
    sort_order: SearchSortOrder = SearchSortOrder.desc,
):
    """
    Search for cart line items by customer name and/or potion sku.
    """
    sort_columns = {
        SearchSortOptions.customer_name: "carts.customer_name",
        SearchSortOptions.item_sku: "potion_mixtures.sku",
        SearchSortOptions.line_item_total: "line_item_total",
        SearchSortOptions.timestamp: "carts.created_at",
    }

    with db.engine.begin() as connection:
        rows = connection.execute(
            sqlalchemy.text(f"""
                SELECT
                    cart_items.id AS line_item_id,
                    potion_mixtures.sku AS item_sku,
                    carts.customer_name,
                    cart_items.quantity * potion_mixtures.price AS line_item_total,
                    carts.created_at AS timestamp
                FROM carts
                JOIN cart_items ON carts.id = cart_items.cart_id
                JOIN potion_mixtures ON cart_items.potion_mixture_id = potion_mixtures.id
                WHERE (:customer_name = '' OR carts.customer_name ILIKE :customer_filter)
                  AND (:potion_sku = '' OR potion_mixtures.sku ILIKE :potion_filter)
                ORDER BY {sort_columns[sort_col]} {"ASC" if sort_order == SearchSortOrder.asc else "DESC"}
                OFFSET :search_page
            """),
            {
                "customer_name": customer_name,
                "potion_sku": potion_sku,
                "customer_filter": f"%{customer_name}%",
                "potion_filter": f"%{potion_sku}%",
                "search_page": search_page,
            },
        ).all()

    return SearchResponse(
        previous=None,
        next=None,
        results=[
            LineItem(
                line_item_id=row.line_item_id,
                item_sku=row.item_sku,
                customer_name=row.customer_name,
                line_item_total=row.line_item_total,
                timestamp=row.timestamp.isoformat(),
            )
            for row in rows
        ],
    )


class Customer(BaseModel):
    customer_id: str
    customer_name: str
    character_class: str
    character_species: str
    level: int = Field(ge=1, le=20)


@router.post("/visits/{visit_id}", status_code=status.HTTP_204_NO_CONTENT)
def post_visits(visit_id: int, customers: List[Customer]):
    """
    Shares the customers that visited the store on that tick.
    """
    print(customers)
    pass


class CartCreateResponse(BaseModel):
    cart_id: int


@router.post("/", response_model=CartCreateResponse)
def create_cart(new_cart: Customer):
    """
    Creates a new cart for a specific customer.
    """
    with db.engine.begin() as connection:
        cart_id = connection.execute(
            sqlalchemy.text("""
                INSERT INTO carts
                    (customer_id, customer_name, character_class, character_species, level)
                VALUES
                    (:customer_id, :customer_name, :character_class, :character_species, :level)
                RETURNING id
                """),
            new_cart.model_dump(),
        ).scalar_one()
    return CartCreateResponse(cart_id=cart_id)


class CartItem(BaseModel):
    quantity: int = Field(ge=1, description="Quantity must be at least 1")


@router.post("/{cart_id}/items/{item_sku}", status_code=status.HTTP_204_NO_CONTENT)
def set_item_quantity(cart_id: int, item_sku: str, cart_item: CartItem):
    with db.engine.begin() as connection:
        mixture_id = connection.execute(
            sqlalchemy.text("SELECT id FROM potion_mixtures WHERE sku = :sku"),
            {"sku": item_sku},
        ).scalar_one_or_none()
        if mixture_id is None:
            raise HTTPException(status_code=404, detail="Potion not found")

        cart_exists = connection.execute(
            sqlalchemy.text("SELECT EXISTS (SELECT 1 FROM carts WHERE id = :cart_id)"),
            {"cart_id": cart_id},
        ).scalar_one()
        if not cart_exists:
            raise HTTPException(status_code=404, detail="Cart not found")

        connection.execute(
            sqlalchemy.text("""
                UPDATE cart_items
                SET quantity = :quantity
                WHERE cart_id = :cart_id AND potion_mixture_id = :mixture_id
            """),
            {
                "cart_id": cart_id,
                "mixture_id": mixture_id,
                "quantity": cart_item.quantity,
            },
        )

        connection.execute(
            sqlalchemy.text("""
                INSERT INTO cart_items (
                    cart_id, potion_mixture_id, quantity, customer_id
                )
                SELECT :cart_id, :mixture_id, :quantity, customer_id
                FROM carts
                WHERE id = :cart_id
                """),
            {
                "cart_id": cart_id,
                "mixture_id": mixture_id,
                "quantity": cart_item.quantity,
            },
        )
    return status.HTTP_204_NO_CONTENT


class CheckoutResponse(BaseModel):
    total_potions_bought: int
    total_gold_paid: int


class CartCheckout(BaseModel):
    payment: str


@router.post("/{cart_id}/checkout", response_model=CheckoutResponse)
def checkout(cart_id: int, cart_checkout: CartCheckout):
    """
    Handles the checkout process for a specific cart.
    """

    with db.engine.begin() as connection:
        cart_exists = connection.execute(
            sqlalchemy.text("SELECT EXISTS (SELECT 1 FROM carts WHERE id = :cart_id)"),
            {"cart_id": cart_id},
        ).scalar_one()
        if not cart_exists:
            raise HTTPException(status_code=404, detail="Cart not found")

        transaction_id = connection.execute(
            sqlalchemy.text("""
            INSERT INTO transactions (request_type, request_id, response, day, hour)
            SELECT :request_type, :request_id, NULL, day, hour
            FROM game_time
            WHERE id = 1
            RETURNING id
        """),
            {"request_type": "checkout", "request_id": cart_id},
        ).scalar_one()
        if transaction_id is None:
            saved = connection.execute(
                sqlalchemy.text("""
                    SELECT response
                    FROM transactions
                    WHERE request_type = :request_type AND request_id = :request_id
                """),
                {"request_type": "checkout", "chec": cart_id},
            ).scalar_one_or_none()
            if saved is not None:
                return CheckoutResponse(**saved)

        total_potions_bought = 0
        total_gold_paid = 0
        entries = []
        rows = connection.execute(
            sqlalchemy.text("""
                SELECT cart_items.quantity, potion_mixtures.sku AS sku,
                       potion_mixtures.price
                               + CASE
                                   WHEN game_time.hour IN (18, 20)
                                        AND potion_mixtures.sku IN (
                                            'ORANGE_JUICE_0',
                                            'POMEGRANATE_SODA_0',
                                            'LIME_JUICE_0',
                                            'DIL_RED_POTION_0'
                                        )
                                   THEN 5
                                   ELSE 0
                                 END AS price
                    FROM cart_items
                    JOIN potion_mixtures ON potion_mixtures.id = cart_items.potion_mixture_id
                    CROSS JOIN game_time
                    WHERE cart_items.cart_id = :cart_id
                """),
            {"cart_id": cart_id},
        ).all()
        for row in rows:
            if (
                connection.execute(
                    sqlalchemy.text("""
                    SELECT COALESCE(SUM(amount), 0) AS balance
                    FROM ledger_entries
                    WHERE resource_type = 'potion' AND resource_key = :resource_key
                """),
                    {"resource_key": row.sku},
                ).scalar_one()
                < row.quantity
            ):
                raise HTTPException(
                    status_code=409, detail="Insufficient potion inventory"
                )
            entries.append(("potion", row.sku, -row.quantity))
            total_potions_bought += row.quantity
            total_gold_paid += row.price * row.quantity

        entries.append(("inventory", "gold", total_gold_paid))
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
        response = {
            "total_potions_bought": total_potions_bought,
            "total_gold_paid": total_gold_paid,
        }

        print(f"response: {response}")
        connection.execute(
            sqlalchemy.text("""
                    UPDATE transactions
                    SET response = CAST(:response AS jsonb)
                    WHERE id = :transaction_id
                """),
            {"transaction_id": transaction_id, "response": json.dumps(response)},
        )

    return CheckoutResponse(**response)
