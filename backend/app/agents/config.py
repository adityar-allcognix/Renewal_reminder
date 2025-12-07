"""
AI Agents Configuration
=======================
Re-exports settings from main backend config for use by agent modules.
"""

# Import from main backend config
from ..config import settings, get_settings

__all__ = ["settings", "get_settings"]
