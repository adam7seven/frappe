from typing import Union

from typing_extensions import override


class DocRef:
    """A lightweight reference to a document, containing just the doctype and id."""

    def __init__(self, doctype: str, id: str):
        self.doctype = doctype
        self.id = id

    def __value__(self) -> str:
        # Used when requiring its value representation for db interactions, serializations, etc
        return self.id

    @override
    def __hash__(self: Union[type, "DocRef"]) -> int:
        if isinstance(self, type):
            raise TypeError("Only document instances can be hashed.")
        try:
            id = self.id
        except AttributeError:
            raise TypeError("Partially instantiated document instances can't be hashed.")
        if id:
            return hash(self.doctype + id)
        raise TypeError(f"Only named documents can be hashed; maybe the document ({self.doctype}) is unsaved.")

    @override
    def __str__(self) -> str:
        return f"{self.doctype} ({self.id or 'n/a'})"

    @override
    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}: doctype={self.doctype} id={self.id or 'n/a'}>"
