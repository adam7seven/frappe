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
	def __str__(self) -> str:
		return f"{self.doctype} ({self.id or 'n/a'})"

	@override
	def __repr__(self) -> str:
		return f"<{self.__class__.__name__}: doctype={self.doctype} id={self.id or 'n/a'}>"
