# Copyright (c) 2025, Frappe Technologies and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document


class QuantityCompleteDefinitionItem(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		baseid_field: DF.Literal[None]
		basetype_field: DF.Literal[None]
		complete_logic: DF.Data | None
		direction: DF.Literal["1", "-1"]
		id: DF.Int | None
		main_doctype: DF.Link
		parent: DF.Data
		parentfield: DF.Data
		parenttype: DF.Data
		qty_doctype: DF.Literal[None]
		qty_field: DF.Literal[None]
	# end: auto-generated types

	pass
