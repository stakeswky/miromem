"""Regression test for the gateway Polymarket proxy route."""

from __future__ import annotations

from miromem.gateway.app import app


def test_gateway_registers_polymarket_proxy_route() -> None:
    matching_routes = [
        route
        for route in app.routes
        if getattr(route, "path", None) == "/api/polymarket/{path:path}"
    ]

    assert len(matching_routes) == 1
    assert "GET" in matching_routes[0].methods
