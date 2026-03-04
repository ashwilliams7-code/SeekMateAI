"""
SeekMate Long-Form Application Engine

Handles external job applications from SEEK that redirect to employer ATS portals.
Completes multi-page forms, uploads documents, solves CAPTCHAs, and handles email verification.
"""

from longform.engine import LongFormEngine
from longform.fill_planner import FillPlanner, FillPlan, FillAction
from longform.field_logger import FieldLogger
from longform.label_normalizer import normalize_label

__all__ = ["LongFormEngine", "FillPlanner", "FillPlan", "FillAction",
           "FieldLogger", "normalize_label"]
__version__ = "2.0.0"
