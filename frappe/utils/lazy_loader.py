import importlib.util
import sys


def lazy_import(id, package=None):
    """Import a module lazily.

    The module is loaded when modules's attribute is accessed for the first time.
    This works with both absolute and relative imports.
    $ cat mod.py
    print("Loading mod.py")
    $ python -i lazy_loader.py
    >>> mod = lazy_import("mod")  # Module is not loaded
    >>> mod.__str__()  # module is loaded on accessing attribute
    Loading mod.py
    "<module 'mod' from '.../frappe/utils/mod.py'>"
    >>>

    Code based on https://github.com/python/cpython/blob/master/Doc/library/importlib.rst#implementing-lazy-imports.
    """
    # Return if the module already loaded
    if id in sys.modules:
        return sys.modules[id]

    # Find the spec if not loaded
    spec = importlib.util.find_spec(id, package)
    if not spec:
        raise ImportError(f"Module {id} Not found.")

    loader = importlib.util.LazyLoader(spec.loader)
    spec.loader = loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[id] = module
    loader.exec_module(module)
    return module
