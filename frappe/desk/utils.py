# Copyright (c) 2020, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import frappe


def validate_route_conflict(doctype, id):
	"""
	Raises exception if id clashes with routes from other documents for /app routing
	"""

	if frappe.flags.in_migrate:
		return

	all_ids = []
	for _doctype in ["Page", "Workspace", "DocType"]:
		all_ids.extend(
			[slug(d) for d in frappe.get_all(_doctype, pluck="id") if (doctype != _doctype and d != id)]
		)

	if slug(id) in all_ids:
		frappe.msgprint(frappe._("ID already taken, please set a new id"))
		raise frappe.IDError


def slug(id):
	return id.lower().replace(" ", "-")


def pop_csv_params(form_dict):
	"""Pop csv params from form_dict and return them as a dict."""
	from csv import QUOTE_NONNUMERIC

	from frappe.utils.data import cint, cstr

	return {
		"delimiter": cstr(form_dict.pop("csv_delimiter", ","))[0],
		"quoting": cint(form_dict.pop("csv_quoting", QUOTE_NONNUMERIC)),
		"decimal_sep": cstr(form_dict.pop("csv_decimal_sep", ".")),
	}


def get_csv_bytes(data: list[list], csv_params: dict) -> bytes:
	"""Convert data to csv bytes."""
	from csv import writer
	from io import StringIO

	decimal_sep = csv_params.pop("decimal_sep", None)

	_data = data.copy()
	if decimal_sep:
		_data = apply_csv_decimal_sep(data, decimal_sep)

	file = StringIO()
	csv_writer = writer(file, **csv_params)
	csv_writer.writerows(_data)

	return file.getvalue().encode("utf-8")


def apply_csv_decimal_sep(data: list[list], decimal_sep: str) -> list[list]:
	"""Apply decimal separator to csv data."""
	if decimal_sep == ".":
		return data

	return [
		[str(value).replace(".", decimal_sep, 1) if isinstance(value, float) else value for value in row]
		for row in data
	]


def provide_binary_file(filename: str, extension: str, content: bytes) -> None:
	"""Provide a binary file to the client."""
	from frappe import _

	frappe.response["type"] = "binary"
	frappe.response["filecontent"] = content
	frappe.response["filename"] = f"{_(filename)}.{extension}"
