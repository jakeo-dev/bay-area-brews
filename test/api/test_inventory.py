from src.api.inventory import CapacityPlan, get_capacity_plan


def test_capacity_plan() -> None:
    capacity_plan = get_capacity_plan()

    assert isinstance(capacity_plan, CapacityPlan)
    assert capacity_plan.potion_capacity == 0
    assert capacity_plan.ml_capacity == 0
