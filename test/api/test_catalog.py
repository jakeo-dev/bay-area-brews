from src.api.catalog import CatalogItem, create_catalog


def test_create_catalog() -> None:
    catalog = create_catalog(
        red_potions=10,
        green_potions=5,
        blue_potions=0,
    )

    assert isinstance(catalog, list)
    assert len(catalog) == 2
    assert catalog[0].sku == "RED_POTION_0"
    assert catalog[0].quantity == 10
    assert catalog[1].sku == "GREEN_POTION_0"
    assert catalog[1].quantity == 5
