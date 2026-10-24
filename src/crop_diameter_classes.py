"""Compatibility facade for the T01 diameter policy operations.

Implementation lives by responsibility in crop_diameter_selection,
crop_square_recess and crop_owner_review. Existing scripts retain this import.
"""
from src.crop_diameter_selection import admissible_diameters, select_targets, promote_round_priorities
from src.crop_square_recess import square_guided_recess
from src.crop_owner_review import select_owner_review_targets

__all__ = [
    "admissible_diameters",
    "select_targets",
    "promote_round_priorities",
    "square_guided_recess",
    "select_owner_review_targets",
]
