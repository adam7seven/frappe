# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import frappe
from frappe.model.document import Document

DEFAULT_ENABLED_CURRENCIES = ("INR", "USD", "GBP", "EUR", "AED", "AUD", "JPY", "CNY", "CHF")


class Currency(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		currency_id: DF.Data
		currency_name: DF.Data
		enabled: DF.Check
		fraction: DF.Data | None
		fraction_units: DF.Int
		number_format: DF.Literal[
			"",
			"#,###.##",
			"#.###,##",
			"# ###.##",
			"# ###,##",
			"#'###.##",
			"#, ###.##",
			"#,##,###.##",
			"#,###.###",
			"#.###",
			"#,###",
		]
		smallest_currency_fraction_value: DF.Currency
		symbol: DF.Data | None
		symbol_on_right: DF.Check
	# end: auto-generated types

	def before_validate(self):
		if not self.currency_name and self.id:
			self.currency_name = self.id

	# NOTE: During installation country docs are bulk inserted.
	def validate(self):
		frappe.clear_cache()


def enable_default_currencies():
	frappe.db.set_value("Currency", {"id": ("in", DEFAULT_ENABLED_CURRENCIES)}, "enabled", 1)
