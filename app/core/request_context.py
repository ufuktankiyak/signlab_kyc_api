"""
Request-scoped context using contextvars.

Set in middleware, read anywhere in the same async/sync call chain.
"""

from contextvars import ContextVar

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)
user_id_var: ContextVar[int | None] = ContextVar("user_id", default=None)
tx_id_var: ContextVar[str | None] = ContextVar("tx_id", default=None)
client_ip_var: ContextVar[str | None] = ContextVar("client_ip", default=None)


def get_log_context() -> dict:
    """Return current request context as a dict suitable for log `extra`."""
    ctx = {}
    for key, var in (
        ("request_id", request_id_var),
        ("user_id", user_id_var),
        ("tx_id", tx_id_var),
        ("client_ip", client_ip_var),
    ):
        val = var.get()
        if val is not None:
            ctx[key] = val
    return ctx
