import importlib
import inspect
import pkgutil

import msgspec
import pytest

import claimvoice.schemas as schemas_pkg
from claimvoice.schemas.base import Model

MODULES = [importlib.import_module(f"claimvoice.schemas.{m.name}") for m in pkgutil.iter_modules(schemas_pkg.__path__)]
STRUCTS = sorted(
    {
        obj
        for module in MODULES
        for _, obj in inspect.getmembers(module, inspect.isclass)
        if issubclass(obj, msgspec.Struct) and obj.__module__ == module.__name__
    },
    key=lambda c: c.__qualname__,
)


@pytest.mark.parametrize("struct", STRUCTS, ids=lambda c: c.__qualname__)
def test_every_wire_struct_resolves_to_a_json_schema(struct):
    msgspec.json.schema(struct)


def test_wire_keys_are_camel_case():
    from claimvoice.schemas.calls import LiveLine

    props = msgspec.json.schema(LiveLine)["$defs"]["LiveLine"]["properties"]
    assert "callerPhoneMasked" in props and "caller_phone_masked" not in props
    assert all(issubclass(s, Model) or s.__module__.endswith("voice") for s in STRUCTS)
