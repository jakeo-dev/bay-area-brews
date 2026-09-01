from src.api.carts import CartCreateResponse, Customer, create_cart


def test_carts_checkout() -> None:
    customer: Customer = Customer(
        customer_id="1234567890",
        customer_name="Jake",
        character_class="Something",
        character_species="Human",
        level=1,
    )

    cart = create_cart(customer)

    assert isinstance(cart, CartCreateResponse)
    assert cart.cart_id > 0
