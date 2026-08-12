"""
Unit tests for surfacing Space.spaceUri — the Chat web URL for a space.

The Chat API returns spaceUri ("Output only. The URI for a user to access the
space") on the Space resource. Tools that hand a space back to the caller should
pass that link through instead of making the caller construct one — DM and named
space URLs do not share a path format, so building them by hand is guesswork.
"""

import os
import sys

import pytest
from unittest.mock import Mock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

SPACE_URI = "https://chat.google.com/room/AAQAtest/abc"


def _unwrap(tool):
    """Unwrap a FunctionTool + decorator chain to the original async function."""
    fn = getattr(tool, "fn", tool)
    while hasattr(fn, "__wrapped__"):
        fn = fn.__wrapped__
    return fn


def _find_dm_service(space):
    service = Mock()
    service.spaces().findDirectMessage().execute.return_value = space
    return service


def _setup_service(space):
    service = Mock()
    service.spaces().setup().execute.return_value = space
    service.spaces().setup.reset_mock()
    return service


# ---------------------------------------------------------------------------
# link is surfaced when the API provides it
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_find_direct_message_surfaces_space_uri():
    service = _find_dm_service({"name": "spaces/DM1", "spaceUri": SPACE_URI})

    from gchat.chat_tools import find_direct_message

    result = await _unwrap(find_direct_message)(
        service=service,
        user_google_email="me@example.com",
        user_id="other@example.com",
    )

    assert "spaces/DM1" in result
    assert SPACE_URI in result


@pytest.mark.asyncio
async def test_create_direct_message_surfaces_space_uri():
    service = _setup_service({"name": "spaces/DM2", "spaceUri": SPACE_URI})

    from gchat.chat_tools import create_direct_message

    result = await _unwrap(create_direct_message)(
        service=service,
        user_google_email="me@example.com",
        user_id="other@example.com",
    )

    assert "spaces/DM2" in result
    assert SPACE_URI in result


@pytest.mark.asyncio
async def test_create_space_surfaces_space_uri():
    service = _setup_service({"name": "spaces/ROOM1", "spaceUri": SPACE_URI})

    from gchat.chat_tools import create_space

    result = await _unwrap(create_space)(
        service=service,
        user_google_email="me@example.com",
        display_name="Team Room",
    )

    assert "spaces/ROOM1" in result
    assert SPACE_URI in result


# ---------------------------------------------------------------------------
# absent link must not break the response
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_find_direct_message_without_space_uri_still_returns_id():
    service = _find_dm_service({"name": "spaces/DM3"})

    from gchat.chat_tools import find_direct_message

    result = await _unwrap(find_direct_message)(
        service=service,
        user_google_email="me@example.com",
        user_id="other@example.com",
    )

    assert "spaces/DM3" in result
    assert "None" not in result
    assert "http" not in result


@pytest.mark.asyncio
async def test_create_direct_message_without_space_uri_still_returns_id():
    service = _setup_service({"name": "spaces/DM4"})

    from gchat.chat_tools import create_direct_message

    result = await _unwrap(create_direct_message)(
        service=service,
        user_google_email="me@example.com",
        user_id="other@example.com",
    )

    assert "spaces/DM4" in result
    assert "None" not in result
    assert "http" not in result


@pytest.mark.asyncio
async def test_create_space_without_space_uri_still_returns_id():
    service = _setup_service({"name": "spaces/ROOM2"})

    from gchat.chat_tools import create_space

    result = await _unwrap(create_space)(
        service=service,
        user_google_email="me@example.com",
        display_name="Team Room",
    )

    assert "spaces/ROOM2" in result
    assert "None" not in result
    assert "http" not in result
