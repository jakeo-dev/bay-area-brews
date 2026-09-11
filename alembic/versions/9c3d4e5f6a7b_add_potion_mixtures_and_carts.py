"""Add potion mixtures and database-backed carts.

Revision ID: 9c3d4e5f6a7b
Revises: 4d517ad2b3d0
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "9c3d4e5f6a7b"
down_revision: Union[str, None] = "4d517ad2b3d0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS potion_mixtures (
            id SERIAL PRIMARY KEY,
            sku VARCHAR(20) NOT NULL UNIQUE,
            name VARCHAR(100) NOT NULL,
            red_amount INTEGER NOT NULL,
            green_amount INTEGER NOT NULL,
            blue_amount INTEGER NOT NULL,
            dark_amount INTEGER NOT NULL,
            price INTEGER NOT NULL,
            number INTEGER NOT NULL DEFAULT 0,
            CONSTRAINT uq_potion_mixtures_amounts
                UNIQUE (red_amount, green_amount, blue_amount, dark_amount),
            CONSTRAINT ck_potion_mixtures_amounts_sum
                CHECK (red_amount + green_amount + blue_amount + dark_amount = 100),
            CONSTRAINT ck_potion_mixtures_price_non_negative CHECK (price >= 0),
            CONSTRAINT ck_potion_mixtures_number_non_negative CHECK (number >= 0)
        )
    """))

    op.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS carts (
            id SERIAL PRIMARY KEY,
            customer_id VARCHAR(100) NOT NULL,
            customer_name VARCHAR(100) NOT NULL,
            character_class VARCHAR(100) NOT NULL,
            character_species VARCHAR(100) NOT NULL,
            level INTEGER NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT ck_carts_level CHECK (level >= 1 AND level <= 20)
        )
    """))
    op.execute(sa.text("""
        ALTER TABLE carts
            ALTER COLUMN customer_id TYPE VARCHAR(100) USING customer_id::text,
            ADD COLUMN IF NOT EXISTS customer_name VARCHAR(100),
            ADD COLUMN IF NOT EXISTS character_class VARCHAR(100),
            ADD COLUMN IF NOT EXISTS character_species VARCHAR(100),
            ADD COLUMN IF NOT EXISTS level INTEGER,
            ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT now()
    """))
    op.execute(sa.text("""
        UPDATE carts
        SET customer_name = COALESCE(customer_name, ''),
            character_class = COALESCE(character_class, ''),
            character_species = COALESCE(character_species, ''),
            level = COALESCE(level, 1)
    """))
    op.execute(sa.text("""
        ALTER TABLE carts
            ALTER COLUMN customer_name SET NOT NULL,
            ALTER COLUMN character_class SET NOT NULL,
            ALTER COLUMN character_species SET NOT NULL,
            ALTER COLUMN level SET NOT NULL
    """))

    op.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS cart_items (
            id SERIAL PRIMARY KEY,
            cart_id INTEGER NOT NULL,
            potion_mixture_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL,
            CONSTRAINT uq_cart_items_cart_mixture UNIQUE (cart_id, potion_mixture_id),
            CONSTRAINT ck_cart_items_quantity CHECK (quantity >= 1)
        )
    """))
    op.execute(sa.text("""
        ALTER TABLE cart_items
            ADD COLUMN IF NOT EXISTS cart_id INTEGER,
            ADD COLUMN IF NOT EXISTS potion_mixture_id INTEGER,
            ADD COLUMN IF NOT EXISTS quantity INTEGER
    """))
    op.execute(sa.text("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint WHERE conname = 'fk_cart_items_cart_id'
            ) THEN
                ALTER TABLE cart_items ADD CONSTRAINT fk_cart_items_cart_id
                    FOREIGN KEY (cart_id) REFERENCES carts(id) ON DELETE CASCADE;
            END IF;
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint WHERE conname = 'fk_cart_items_potion_mixture_id'
            ) THEN
                ALTER TABLE cart_items ADD CONSTRAINT fk_cart_items_potion_mixture_id
                    FOREIGN KEY (potion_mixture_id) REFERENCES potion_mixtures(id);
            END IF;
        END $$
    """))


def downgrade() -> None:
    op.drop_table("cart_items")
    op.drop_table("carts")
    op.execute(sa.text("DROP TABLE IF EXISTS potion_mixtures"))
