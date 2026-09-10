"""Consecutive customer runs. Never sort or drop submitted order-level values."""

from dataclasses import dataclass


@dataclass
class ClientGroup:
    orders: list
    client: str
    common_phone: str | None


def phone_text(order):
    phone = order.get("company_phone")
    return phone if phone and phone.strip() else "не е посочен"


def group_orders(orders):
    runs = []
    previous = None
    for index, order in enumerate(orders, 1):
        key = (
            ("id", order["client_id"], order["client"])
            if "client_id" in order
            else ("name", order["client"])
        )
        if key != previous:
            runs.append([])
        runs[-1].append((index, order))
        previous = key
    groups = []
    for run in runs:
        phones = {phone_text(order) for _, order in run}
        groups.append(
            ClientGroup(
                run,
                run[0][1]["client"],
                next(iter(phones)) if len(phones) == 1 else None,
            )
        )
    return groups
