"""
SeekMate Long-Form Application Engine

Handles external job applications from SEEK that redirect to employer ATS portals.
Completes multi-page forms, uploads documents, solves CAPTCHAs, and handles email verification.
"""

from longform.engine import LongFormEngine

__all__ = ["LongFormEngine"]
__version__ = "1.0.0"
