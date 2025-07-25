# Copyright (c) 2019, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
import os
from functools import wraps
from os.path import join

import frappe
from frappe import _
from frappe.modules.import_file import import_file_by_path
from frappe.utils import cint, get_link_to_form


def cache_source(function):
	@wraps(function)
	def wrapper(*args, **kwargs):
		if kwargs.get("chart_id"):
			chart = frappe.get_doc("Dashboard Chart", kwargs.get("chart_id"))
		else:
			chart = kwargs.get("chart")
		no_cache = kwargs.get("no_cache")
		if no_cache:
			return function(chart=chart, no_cache=no_cache)
		chart_id = frappe.parse_json(chart).id
		cache_key = f"chart-data:{chart_id}"
		if cint(kwargs.get("refresh")):
			results = generate_and_cache_results(kwargs, function, cache_key, chart)
		else:
			cached_results = frappe.cache.get_value(cache_key)
			if cached_results:
				results = frappe.parse_json(frappe.safe_decode(cached_results))
			else:
				results = generate_and_cache_results(kwargs, function, cache_key, chart)
		return results

	return wrapper


def generate_and_cache_results(args, function, cache_key, chart):
	try:
		args = frappe._dict(args)
		results = function(
			chart_id=args.chart_id,
			filters=args.filters or None,
			from_date=args.from_date or None,
			to_date=args.to_date or None,
			time_interval=args.time_interval or None,
			timespan=args.timespan or None,
			heatmap_year=args.heatmap_year or None,
		)
	except TypeError as e:
		if str(e) == "'NoneType' object is not iterable":
			# Probably because of invalid link filter
			#
			# Note: Do not try to find the right way of doing this because
			# it results in an inelegant & inefficient solution
			# ref: https://github.com/frappe/frappe/pull/9403
			frappe.throw(
				_("Please check the filter values set for Dashboard Chart: {}").format(
					get_link_to_form(chart.doctype, chart.id)
				),
				title=_("Invalid Filter Value"),
			)
			return
		else:
			raise

	if not frappe.flags.read_only:
		frappe.db.set_value(
			"Dashboard Chart", args.chart_id, "last_synced_on", frappe.utils.now(), update_modified=False
		)
	return results


def get_dashboards_with_link(docid, doctype):
	links = []

	if doctype == "Dashboard Chart":
		links = frappe.get_all("Dashboard Chart Link", fields=["parent"], filters={"chart": docid})
	elif doctype == "Number Card":
		links = frappe.get_all("Number Card Link", fields=["parent"], filters={"card": docid})

	return [link.parent for link in links]


def sync_dashboards(app=None):
	"""Import, overwrite dashboards from `[app]/[app]_dashboard`"""
	apps = [app] if app else frappe.get_installed_apps()

	for app_name in apps:
		print(f"Updating Dashboard for {app_name}")
		for module_id in frappe.local.app_modules.get(app_name) or []:
			frappe.flags.in_import = True
			make_records_in_module(app_name, module_id)
			frappe.flags.in_import = False


def make_records_in_module(app, module):
	dashboards_path = frappe.get_module_path(module, f"{module}_dashboard")
	charts_path = frappe.get_module_path(module, "dashboard chart")
	cards_path = frappe.get_module_path(module, "number card")

	paths = [dashboards_path, charts_path, cards_path]
	for path in paths:
		make_records(path)


def make_records(path, filters=None):
	if os.path.isdir(path):
		for fname in os.listdir(path):
			if os.path.isdir(join(path, fname)):
				if fname == "__pycache__":
					continue
				import_file_by_path(f"{path}/{fname}/{fname}.json")
