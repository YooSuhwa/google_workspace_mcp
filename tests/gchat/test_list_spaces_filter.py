"""
Unit tests for list_spaces' space_type -> Chat API filter translation.

Regression cover: the filter used to be emitted with an unquoted enum value
(`spaceType = SPACE`), which the Chat API rejects with HTTP 400
"Invalid filter query". Only the default "all" (no filter) worked, so both
other values of space_type were unusable.
"""

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


def _service_returning(spaces):
    """Mock Chat service whose spaces().list() returns the given spaces."""
    service = Mock()
    service.spaces().list().execute.return_value = {"spaces": spaces}
    return service


def _list_call_kwargs(service):
    """The kwargs of the spaces().list(...) call that carried the request."""
    # spaces() is called repeatedly by the mock setup; the request call is the
    # last list(...) invocation with actual parameters.
    calls = [c for c in service.spaces().list.call_args_list if c.kwargs]
    assert calls, "spaces().list() was never called with keyword arguments"
    return calls[-1].kwargs


ROOM = {"name": "spaces/A", "displayName": "Room", "spaceType": "SPACE"}
DM = {"name": "spaces/B", "spaceType": "DIRECT_MESSAGE"}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "space_type,expected_filter",
    [
        ("room", 'spaceType = "SPACE"'),
        ("dm", 'spaceType = "DIRECT_MESSAGE"'),
    ],
)
async def test_filter_quotes_enum_value(space_type, expected_filter):
    """The Chat API only accepts the enum value quoted — assert we quote it."""
    from gchat.chat_tools import list_spaces

    service = _service_returning([ROOM])

    await _unwrap(list_spaces)(
        service=service,
        user_google_email="test@example.com",
        space_type=space_type,
    )

    assert _list_call_kwargs(service)["filter"] == expected_filter


@pytest.mark.asyncio
@pytest.mark.parametrize("space_type", ["all", "space", "", "ROOM"])
async def test_no_filter_sent_for_all_and_unrecognized_values(space_type):
    """ "all" and unrecognized values must send no filter, not a broken one."""
    from gchat.chat_tools import list_spaces

    service = _service_returning([ROOM, DM])

    await _unwrap(list_spaces)(
        service=service,
        user_google_email="test@example.com",
        space_type=space_type,
    )

    assert "filter" not in _list_call_kwargs(service)


@pytest.mark.asyncio
async def test_page_size_is_forwarded():
    """page_size reaches the API as pageSize."""
    from gchat.chat_tools import list_spaces

    service = _service_returning([ROOM])

    await _unwrap(list_spaces)(
        service=service,
        user_google_email="test@example.com",
        page_size=7,
    )

    assert _list_call_kwargs(service)["pageSize"] == 7


@pytest.mark.asyncio
async def test_empty_result_reports_the_requested_type():
    """A no-match response names the space_type that was asked for."""
    from gchat.chat_tools import list_spaces

    service = _service_returning([])

    result = await _unwrap(list_spaces)(
        service=service,
        user_google_email="test@example.com",
        space_type="dm",
    )

    assert "No Chat spaces found" in result
    assert "dm" in result
