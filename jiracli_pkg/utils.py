"""Utility functions."""

WORKING_DAYS = {"Monday", "Tuesday", "Wednesday", "Thursday", "Friday"}


def convert_to_hours(time_spent: str) -> float:
    total_hours = 0.0
    parts = time_spent.split()
    for part in parts:
        if part.endswith("w"):
            total_hours += int(part[:-1]) * 7 * 24
        elif part.endswith("d"):
            total_hours += int(part[:-1]) * 24
        elif part.endswith("h"):
            total_hours += int(part[:-1])
        elif part.endswith("m"):
            total_hours += int(part[:-1]) / 60
    return total_hours
