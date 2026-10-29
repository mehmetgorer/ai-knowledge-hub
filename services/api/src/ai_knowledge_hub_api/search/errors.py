"""Semantic search errors."""


class SearchError(Exception):
    """Base search failure."""


class SearchValidationError(SearchError):
    """Invalid search request parameters."""


class SearchEmbeddingError(SearchError):
    """Query embedding failed."""


class SearchDatabaseError(SearchError):
    """Database search query failed."""
