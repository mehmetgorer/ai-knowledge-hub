class AuthenticationError(Exception):
    """Raised when a bearer token is missing, invalid, or untrusted."""


class AuthenticationConfigurationError(Exception):
    """Raised when required authentication settings are not configured."""


class JwksUnavailableError(Exception):
    """Raised when JWKS keys cannot be retrieved."""
