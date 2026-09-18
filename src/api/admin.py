from fastapi import APIRouter, Depends, status
import sqlalchemy
from src.api import auth
from src import database as db

router = APIRouter(
    prefix="/admin",
    tags=["admin"],
    dependencies=[Depends(auth.get_api_key)],
)


@router.post("/reset", status_code=status.HTTP_204_NO_CONTENT)
def reset():
    """
    Reset the game state. Gold goes to 100, all potions are removed from
    inventory, and all barrels are removed from inventory. Carts are all reset.
    """

    with db.engine.begin() as connection:
        transaction_id = connection.execute(sqlalchemy.text("""
            INSERT INTO transactions (request_type, request_id, response)
            VALUES (
                'reset',
                COALESCE((SELECT MAX(request_id) FROM transactions WHERE request_type = 'reset'), 0) + 1,
                NULL
            )
            RETURNING id
        """)).scalar_one()

        inventory_rows = connection.execute(
            sqlalchemy.text("""
                    SELECT resource_key, COALESCE(SUM(amount), 0) AS balance
                    FROM ledger_entries
                    WHERE resource_type = :resource_type
                    GROUP BY resource_key
                """),
            {"resource_type": "inventory"},
        ).all()
        inventory = {row.resource_key: row.balance for row in inventory_rows}

        potion_rows = connection.execute(
            sqlalchemy.text("""
                            SELECT resource_key, COALESCE(SUM(amount), 0) AS balance
                            FROM ledger_entries
                            WHERE resource_type = :resource_type
                            GROUP BY resource_key
                        """),
            {"resource_type": "potion"},
        ).all()

        potion_balances = {row.resource_key: row.balance for row in potion_rows}
        entries = [("inventory", key, -value) for key, value in inventory.items()]
        entries.append(("inventory", "gold", 100))
        entries.extend(
            ("potion", key, -value) for key, value in potion_balances.items()
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
        connection.execute(sqlalchemy.text("DELETE FROM cart_items"))
        connection.execute(sqlalchemy.text("DELETE FROM carts"))
