"""
Unit tests for Google Chat space creation tools — create_direct_message / create_space

Both tools call spaces.setup, which requires the chat.spaces scope. The Chat API
returns an existing DM when one already exists, so create_direct_message is
idempotent by construction and needs no prior findDirectMessage call.
"""

import inspect
import os
import sys

import pytest
from unittest.mock import Mock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))


def _unwrap(tool):
    """Unwrap a FunctionTool + decorator chain to the original async function."""
    fn = getattr(tool, "fn", tool)
    while hasattr(fn, "__wrapped__"):
        fn = fn.__wrapped__
    return fn


def _service_returning(space_name="spaces/NEW"):
    """Build a Chat service mock whose spaces.setup returns the given space name."""
    service = Mock()
    service.spaces().setup().execute.return_value = {"name": space_name}
    # Wiring the mock above already recorded a setup() call; drop it so tests can
    # assert the tool itself never called the API. reset_mock keeps return values.
    service.spaces().setup.reset_mock()
    return service


def _setup_body(service):
    """Extract the request body passed to spaces.setup."""
    return service.spaces().setup.call_args.kwargs["body"]


# ---------------------------------------------------------------------------
# create_direct_message
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_direct_message_wraps_bare_email():
    """A bare email should be wrapped as users/{email} in the membership."""
    service = _service_returning("spaces/DM1")

    from gchat.chat_tools import create_direct_message

    result = await _unwrap(create_direct_message)(
        service=service,
        user_google_email="me@example.com",
        user_id="other@example.com",
    )

    body = _setup_body(service)
    assert body["space"]["spaceType"] == "DIRECT_MESSAGE"
    assert body["space"]["singleUserBotDm"] is False
    assert body["memberships"] == [
        {"member": {"name": "users/other@example.com", "type": "HUMAN"}}
    ]
    assert "spaces/DM1" in result


@pytest.mark.asyncio
async def test_create_direct_message_accepts_prefixed_user_id():
    """An already-prefixed users/{id} must not be double-wrapped."""
    service = _service_returning("spaces/DM2")

    from gchat.chat_tools import create_direct_message

    await _unwrap(create_direct_message)(
        service=service,
        user_google_email="me@example.com",
        user_id="users/123456789",
    )

    body = _setup_body(service)
    assert body["memberships"][0]["member"]["name"] == "users/123456789"


@pytest.mark.asyncio
async def test_create_direct_message_omits_display_name():
    """The Chat API rejects displayName on DIRECT_MESSAGE spaces."""
    service = _service_returning()

    from gchat.chat_tools import create_direct_message

    await _unwrap(create_direct_message)(
        service=service,
        user_google_email="me@example.com",
        user_id="other@example.com",
    )

    space = _setup_body(service)["space"]
    assert "displayName" not in space
    assert "spaceDetails" not in space


@pytest.mark.asyncio
async def test_create_direct_message_returns_existing_space():
    """When a DM already exists the API returns it; the id must be surfaced."""
    service = _service_returning("spaces/EXISTING")

    from gchat.chat_tools import create_direct_message

    result = await _unwrap(create_direct_message)(
        service=service,
        user_google_email="me@example.com",
        user_id="other@example.com",
    )

    assert "spaces/EXISTING" in result


@pytest.mark.asyncio
async def test_create_direct_message_rejects_blank_user_id():
    """A blank target must fail before any API call."""
    service = _service_returning()

    from gchat.chat_tools import create_direct_message

    result = await _unwrap(create_direct_message)(
        service=service,
        user_google_email="me@example.com",
        user_id="   ",
    )

    assert "user_id" in result
    service.spaces().setup.assert_not_called()


# ---------------------------------------------------------------------------
# create_space
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_space_sets_display_name_and_members():
    """A named space carries displayName and one membership per member."""
    service = _service_returning("spaces/ROOM1")

    from gchat.chat_tools import create_space

    result = await _unwrap(create_space)(
        service=service,
        user_google_email="me@example.com",
        display_name="Team Room",
        member_ids=["a@example.com", "users/222"],
    )

    body = _setup_body(service)
    assert body["space"]["spaceType"] == "SPACE"
    assert body["space"]["displayName"] == "Team Room"
    assert body["memberships"] == [
        {"member": {"name": "users/a@example.com", "type": "HUMAN"}},
        {"member": {"name": "users/222", "type": "HUMAN"}},
    ]
    assert "spaces/ROOM1" in result


@pytest.mark.asyncio
async def test_create_space_without_members():
    """A space with no members is valid — the caller is added implicitly."""
    service = _service_returning("spaces/EMPTY")

    from gchat.chat_tools import create_space

    await _unwrap(create_space)(
        service=service,
        user_google_email="me@example.com",
        display_name="Solo Room",
    )

    body = _setup_body(service)
    assert body["memberships"] == []
    assert body["space"]["displayName"] == "Solo Room"


@pytest.mark.asyncio
async def test_create_space_rejects_blank_display_name():
    """A named space requires a display name; fail before calling the API."""
    service = _service_returning()

    from gchat.chat_tools import create_space

    result = await _unwrap(create_space)(
        service=service,
        user_google_email="me@example.com",
        display_name="  ",
    )

    assert "display_name" in result
    service.spaces().setup.assert_not_called()


@pytest.mark.asyncio
async def test_create_space_rejects_too_many_members():
    """The Chat API caps memberships at 49; reject before the call."""
    service = _service_returning()

    from gchat.chat_tools import create_space

    result = await _unwrap(create_space)(
        service=service,
        user_google_email="me@example.com",
        display_name="Big Room",
        member_ids=[f"u{i}@example.com" for i in range(50)],
    )

    assert "49" in result
    service.spaces().setup.assert_not_called()


@pytest.mark.asyncio
async def test_create_space_deduplicates_members():
    """Repeating a member must not produce duplicate memberships."""
    service = _service_returning("spaces/DEDUP")

    from gchat.chat_tools import create_space

    await _unwrap(create_space)(
        service=service,
        user_google_email="me@example.com",
        display_name="Dedup Room",
        member_ids=["a@example.com", "users/a@example.com", "b@example.com"],
    )

    names = [m["member"]["name"] for m in _setup_body(service)["memberships"]]
    assert names == ["users/a@example.com", "users/b@example.com"]


# ---------------------------------------------------------------------------
# Tool surface
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_creation_tools_are_not_marked_read_only():
    """Both tools mutate remote state and must not claim readOnlyHint."""
    import gchat.chat_tools  # noqa: F401 — registers the tools
    from core.server import server

    for name in ("create_direct_message", "create_space"):
        tool = await server.get_tool(name)
        assert tool.annotations is not None
        assert tool.annotations.readOnlyHint is False
        assert tool.annotations.destructiveHint is False


@pytest.mark.asyncio
async def test_create_direct_message_is_marked_idempotent():
    """spaces.setup returns the existing DM, so the tool is idempotent."""
    import gchat.chat_tools  # noqa: F401 — registers the tools
    from core.server import server

    dm_tool = await server.get_tool("create_direct_message")
    space_tool = await server.get_tool("create_space")

    assert dm_tool.annotations.idempotentHint is True
    # Creating a named space twice yields two spaces — not idempotent.
    assert space_tool.annotations.idempotentHint is False


@pytest.mark.asyncio
async def test_create_space_exposes_expected_parameters():
    """Public signature should be display_name + member_ids."""
    from gchat.chat_tools import create_space

    public_fn = getattr(create_space, "fn", create_space)
    params = inspect.signature(public_fn).parameters

    assert "display_name" in params
    assert "member_ids" in params
