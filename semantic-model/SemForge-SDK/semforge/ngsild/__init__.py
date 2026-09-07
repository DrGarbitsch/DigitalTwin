"""NGSI-LD semantics: the data views validation runs against."""

from .views import DataView, ViewStats, build_view, collapse_updates, normalise_empty_lists

__all__ = ['DataView', 'ViewStats', 'build_view', 'collapse_updates', 'normalise_empty_lists']
