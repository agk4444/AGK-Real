"""AGK-Real v2 test mocks.

Because AGK module imports are compiled inline into a single namespace,
a "module function" is just a name in the test module's namespace.
Replacing that name with a :class:`Mock` therefore intercepts every
call to it -- including calls made from imported helper code -- until
the mock is restored.

AGK-level API (injected into every test module by the test runner)::

    create m as Mock
    set m to mock("fetch_price")          # record calls, return None
    set m to mock_return("fetch_price", 42)  # record calls, return 42
    ...
    if m.call_count() != 1:
        raise "expected one call"
    create first_arg as String
    set first_arg to m.call_arg(0, 0)     # arg 0 of call 0
    unmock(m)                             # restore the original

The names ``mock``, ``mock_return`` and ``unmock`` are reserved in test
files (the runner pre-declares them so test code typechecks).

Python-level API: :func:`patch` swaps a name in any namespace dict for
a recording Mock; ``mock.restore()`` (or the AGK ``unmock`` helper)
puts the original back.
"""

from .parser import parse

MOCK_PRELUDE_SRC = '''\
define function mock that takes name as String and returns Mock:
    return None

define function mock_return that takes name as String, value as Object and returns Mock:
    return None

define function unmock that takes m as Mock:
    return None
'''

# Parsed once at import; passed as extra_top_levels when compiling test
# files so the mock helpers typecheck. Bodies are never analyzed or
# generated -- the runner injects real Python implementations.
MOCK_PRELUDE = parse(MOCK_PRELUDE_SRC, filename="<agk-test-prelude>")

#: Names reserved for the mock helpers in test files.
MOCK_NAMES = ("mock", "mock_return", "unmock")


class Mock:
    """A callable stand-in that records every call made to it."""

    def __init__(self, name, original, namespace, return_value=None):
        self._mock_name = name
        self._mock_original = original
        self._mock_namespace = namespace
        self._mock_return_value = return_value
        self._mock_calls = []

    def __call__(self, *args, **kwargs):
        self._mock_calls.append((args, kwargs))
        return self._mock_return_value

    def __repr__(self):
        return (f"<Mock of '{self._mock_name}': "
                f"{len(self._mock_calls)} calls>")

    @property
    def calls(self):
        """List of (args, kwargs) for every recorded call."""
        return list(self._mock_calls)

    def call_count(self):
        """Number of recorded calls."""
        return len(self._mock_calls)

    def call_arg(self, call_index, arg_index):
        """The ``arg_index``-th positional argument of the
        ``call_index``-th call (both 0-based)."""
        return self._mock_calls[call_index][0][arg_index]

    def restore(self):
        """Put the original function back in the namespace."""
        self._mock_namespace[self._mock_name] = self._mock_original


def patch(namespace, name, return_value=None):
    """Replace ``namespace[name]`` with a recording Mock.

    Returns the Mock. Raises ValueError when ``name`` is missing or
    not callable, so a typo fails fast instead of silently mocking
    nothing.
    """
    if name not in namespace:
        raise ValueError(f"mock: no function named '{name}' "
                         f"in this test module")
    original = namespace[name]
    if not callable(original):
        raise ValueError(f"mock: '{name}' is not callable")
    mock = Mock(name, original, namespace, return_value)
    namespace[name] = mock
    return mock


def install_helpers(namespace):
    """AGK-callable mock helpers bound to ``namespace``.

    Returns a dict to merge into the test module's namespace before
    exec: ``mock(name)``, ``mock_return(name, value)``, ``unmock(m)``.
    """
    def _mock(name):
        return patch(namespace, name)

    def _mock_return(name, value):
        return patch(namespace, name, return_value=value)

    def _unmock(m):
        if not isinstance(m, Mock):
            raise ValueError(
                "unmock: expected a Mock from mock()/mock_return()")
        m.restore()

    return {"mock": _mock, "mock_return": _mock_return, "unmock": _unmock}
