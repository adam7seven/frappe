# Copyright (c) 2020, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
# Author - Shivam Mishra <shivam@frappe.io>

from functools import wraps
from json import JSONDecodeError, dumps, loads

import frappe
from frappe import DoesNotExistError, ValidationError, _, _dict
from frappe.boot import get_allowed_pages, get_allowed_reports
from frappe.cache_manager import (
	build_domain_restricted_doctype_cache,
	build_domain_restricted_page_cache,
	build_table_count_cache,
)
from frappe.core.doctype.custom_role.custom_role import get_custom_allowed_roles


def handle_not_exist(fn):
	@wraps(fn)
	def wrapper(*args, **kwargs):
		try:
			return fn(*args, **kwargs)
		except DoesNotExistError:
			frappe.clear_last_message()
			return []

	return wrapper


class Workspace:
	def __init__(self, page, minimal=False):
		self.page_id = page.get("id")
		self.page_title = page.get("title")
		self.public_page = page.get("public")
		self.workspace_manager = "Workspace Manager" in frappe.get_roles()

		self.user = frappe.get_user()
		self.allowed_modules = self.get_cached("user_allowed_modules", self.get_allowed_modules)

		self.doc = frappe.get_cached_doc("Workspace", self.page_id)
		if (
			self.doc
			and self.doc.module
			and self.doc.module not in self.allowed_modules
			and not self.workspace_manager
		):
			raise frappe.PermissionError

		self.can_read = self.get_cached("user_perm_can_read", self.get_can_read_items)

		self.allowed_pages = get_allowed_pages(cache=True)
		self.allowed_reports = get_allowed_reports(cache=True)

		if not minimal:
			if self.doc.content:
				self.onboarding_list = [
					x["data"]["onboarding_name"] for x in loads(self.doc.content) if x["type"] == "onboarding"
				]
			self.onboardings = []

			self.table_counts = get_table_with_counts()
		self.restricted_doctypes = (
			frappe.cache.get_value("domain_restricted_doctypes") or build_domain_restricted_doctype_cache()
		)
		self.restricted_pages = (
			frappe.cache.get_value("domain_restricted_pages") or build_domain_restricted_page_cache()
		)

	def is_permitted(self):
		"""Return true if `Has Role` is not set or the user is allowed."""
		from frappe.utils import has_common

		allowed = [d.role for d in self.doc.roles]

		custom_roles = get_custom_allowed_roles("page", self.doc.id)
		allowed.extend(custom_roles)

		if not allowed:
			return True

		roles = frappe.get_roles()

		if has_common(roles, allowed):
			return True

	def get_cached(self, cache_key, fallback_fn):
		value = frappe.cache.get_value(cache_key, user=frappe.session.user)
		if value is not None:
			return value

		value = fallback_fn()

		# Expire every six hour
		frappe.cache.set_value(cache_key, value, frappe.session.user, 21600)
		return value

	def get_can_read_items(self):
		if not self.user.can_read:
			self.user.build_permissions()

		return self.user.can_read

	def get_allowed_modules(self):
		if not self.user.allow_modules:
			self.user.build_permissions()

		return self.user.allow_modules

	def get_onboarding_doc(self, onboarding):
		# Check if onboarding is enabled
		if not frappe.get_system_settings("enable_onboarding"):
			return None

		if not self.onboarding_list:
			return None

		if frappe.db.get_value("Module Onboarding", onboarding, "is_complete"):
			return None

		doc = frappe.get_doc("Module Onboarding", onboarding)

		# Check if user is allowed
		allowed_roles = set(doc.get_allowed_roles())
		user_roles = set(frappe.get_roles())
		if not allowed_roles & user_roles:
			return None

		# Check if already complete
		if doc.check_completion():
			return None

		return doc

	def is_item_allowed(self, id, item_type):
		if frappe.session.user == "Administrator":
			return True

		item_type = item_type.lower()

		if item_type == "doctype":
			return id in (self.can_read or []) and id in (self.restricted_doctypes or [])
		if item_type == "page":
			return id in self.allowed_pages and id in self.restricted_pages
		if item_type == "report":
			return id in self.allowed_reports
		if item_type == "help":
			return True
		if item_type == "dashboard":
			return True
		if item_type == "url":
			return True

		return False

	def build_workspace(self):
		self.cards = {"items": self.get_links()}
		self.charts = {"items": self.get_charts()}
		self.shortcuts = {"items": self.get_shortcuts()}
		self.onboardings = {"items": self.get_onboardings()}
		self.quick_lists = {"items": self.get_quick_lists()}
		self.number_cards = {"items": self.get_number_cards()}
		self.custom_blocks = {"items": self.get_custom_blocks()}

	def _doctype_contains_a_record(self, id):
		exists = self.table_counts.get(id, False)

		if not exists and frappe.db.exists(id):
			if not frappe.db.get_value("DocType", id, "issingle"):
				exists = bool(frappe.get_all(id, limit=1))
			else:
				exists = True
			self.table_counts[id] = exists

		return exists

	def _prepare_item(self, item):
		if item.dependencies:
			dependencies = [dep.strip() for dep in item.dependencies.split(",")]

			incomplete_dependencies = [d for d in dependencies if not self._doctype_contains_a_record(d)]

			if len(incomplete_dependencies):
				item.incomplete_dependencies = incomplete_dependencies
			else:
				item.incomplete_dependencies = ""

		if item.onboard:
			# Mark Spotlights for initial
			if item.get("type") == "doctype":
				id = item.get("id")
				count = self._doctype_contains_a_record(id)

				item["count"] = count

		if item.get("link_type") == "DocType":
			item["description"] = frappe.get_meta(item.link_to).description

		# Translate label
		item["label"] = _(item.label) if item.label else _(item.id)

		return item

	def is_custom_block_permitted(self, custom_block_id):
		from frappe.utils import has_common

		allowed = [
			d.role for d in frappe.get_all("Has Role", fields=["role"], filters={"parent": custom_block_id})
		]

		if not allowed:
			return True

		roles = frappe.get_roles()

		if has_common(roles, allowed):
			return True

		return False

	@handle_not_exist
	def get_links(self):
		cards = self.doc.get_link_groups()

		if not self.doc.hide_custom:
			cards = cards + get_custom_reports_and_doctypes(self.doc.module)

		default_country = frappe.db.get_default("country")

		new_data = []
		for card in cards:
			new_items = []
			card = _dict(card)

			links = card.get("links", [])

			for item in links:
				item = _dict(item)

				# Condition: based on country
				if item.country and item.country != default_country:
					continue

				# Check if user is allowed to view
				if self.is_item_allowed(item.link_to, item.link_type):
					prepared_item = self._prepare_item(item)
					new_items.append(prepared_item)

			if new_items:
				if isinstance(card, _dict):
					new_card = card.copy()
				else:
					new_card = card.as_dict().copy()
				new_card["links"] = new_items
				new_card["label"] = _(new_card["label"])
				new_data.append(new_card)

		return new_data

	@handle_not_exist
	def get_charts(self):
		all_charts = []
		if frappe.has_permission("Dashboard Chart", throw=False):
			charts = self.doc.charts

			for chart in charts:
				if frappe.has_permission("Dashboard Chart", doc=chart.chart_id):
					# Translate label
					chart.label = _(chart.label) if chart.label else _(chart.chart_id)
					all_charts.append(chart)

		return all_charts

	@handle_not_exist
	def get_shortcuts(self):
		def _in_active_domains(item):
			if not item.restrict_to_domain:
				return True
			else:
				return item.restrict_to_domain in frappe.get_active_domains()

		items = []
		shortcuts = self.doc.shortcuts

		for item in shortcuts:
			new_item = item.as_dict().copy()
			if self.is_item_allowed(item.link_to, item.type) and _in_active_domains(item):
				if item.type == "Report":
					report = self.allowed_reports.get(item.link_to, {})
					if report.get("report_type") in ["Query Report", "Script Report", "Custom Report"]:
						new_item["is_query_report"] = 1
					else:
						new_item["ref_doctype"] = report.get("ref_doctype")

				# Translate label
				new_item["label"] = _(item.label) if item.label else _(item.link_to)

				items.append(new_item)

		return items

	@handle_not_exist
	def get_quick_lists(self):
		items = []
		quick_lists = self.doc.quick_lists

		for item in quick_lists:
			if self.is_item_allowed(item.document_type, "doctype"):
				new_item = item.as_dict().copy()

				# Translate label
				new_item["label"] = _(item.label) if item.label else _(item.document_type)

				items.append(new_item)

		return items

	@handle_not_exist
	def get_onboardings(self):
		if self.onboarding_list:
			for onboarding in self.onboarding_list:
				onboarding_doc = self.get_onboarding_doc(onboarding)
				if onboarding_doc:
					item = {
						"label": _(onboarding),
						"title": _(onboarding_doc.title),
						"subtitle": _(onboarding_doc.subtitle),
						"success": _(onboarding_doc.success_message),
						"docs_url": onboarding_doc.documentation_url,
						"items": self.get_onboarding_steps(onboarding_doc),
					}
					self.onboardings.append(item)
		return self.onboardings

	@handle_not_exist
	def get_onboarding_steps(self, onboarding_doc):
		steps = []
		for doc in onboarding_doc.get_steps():
			step = doc.as_dict().copy()
			step.label = _(doc.title)
			step.description = _(doc.description)
			if step.action == "Create Entry":
				step.is_submittable = frappe.db.get_value(
					"DocType", step.reference_document, "is_submittable", cache=True
				)
			steps.append(step)

		return steps

	@handle_not_exist
	def get_number_cards(self):
		all_number_cards = []
		if frappe.has_permission("Number Card", throw=False):
			number_cards = self.doc.number_cards
			for number_card in number_cards:
				if frappe.has_permission("Number Card", doc=number_card.number_card_id):
					# Translate label
					number_card.label = (
						_(number_card.label) if number_card.label else _(number_card.number_card_id)
					)
					all_number_cards.append(number_card)

		return all_number_cards

	@handle_not_exist
	def get_custom_blocks(self):
		all_custom_blocks = []
		if frappe.has_permission("Custom HTML Block", throw=False):
			custom_blocks = self.doc.custom_blocks

			for custom_block in custom_blocks:
				if frappe.has_permission("Custom HTML Block", doc=custom_block.custom_block_id):
					if not self.is_custom_block_permitted(custom_block.custom_block_id):
						continue

					# Translate label
					custom_block.label = (
						_(custom_block.label) if custom_block.label else _(custom_block.custom_block_id)
					)
					all_custom_blocks.append(custom_block)

		return all_custom_blocks


@frappe.whitelist()
@frappe.read_only()
def get_desktop_page(page):
	"""Apply permissions, customizations and return the configuration for a page on desk.

	Args:
			page (json): page data

	Return:
			dict: dictionary of cards, charts and shortcuts to be displayed on website
	"""
	try:
		workspace = Workspace(loads(page))
		workspace.build_workspace()
		return {
			"charts": workspace.charts,
			"shortcuts": workspace.shortcuts,
			"cards": workspace.cards,
			"onboardings": workspace.onboardings,
			"quick_lists": workspace.quick_lists,
			"number_cards": workspace.number_cards,
			"custom_blocks": workspace.custom_blocks,
		}
	except DoesNotExistError:
		frappe.log_error("Workspace Missing")
		return {}


@frappe.whitelist()
def get_workspace_sidebar_items():
	"""Get list of sidebar items for desk"""

	from frappe.modules.utils import get_module_app

	has_access = "Workspace Manager" in frappe.get_roles()

	# don't get domain restricted pages
	blocked_modules = frappe.get_cached_doc("User", frappe.session.user).get_blocked_modules()
	blocked_modules.append("Dummy Module")

	# adding None to allowed_domains to include pages without domain restriction
	allowed_domains = [None, *frappe.get_active_domains()]

	filters = {
		"restrict_to_domain": ["in", allowed_domains],
		"module": ["not in", blocked_modules],
	}

	if has_access:
		filters = []

	# pages sorted based on sequence id
	order_by = "sequence_id asc"
	fields = [
		"id",
		"title",
		"for_user",
		"parent_page",
		"content",
		"public",
		"module",
		"icon",
		"indicator_color",
		"is_hidden",
		"app",
		"type",
		"link_type",
		"link_to",
		"external_link",
	]
	all_pages = frappe.get_all(
		"Workspace", fields=fields, filters=filters, order_by=order_by, ignore_permissions=True
	)
	pages = []
	private_pages = []

	# get additional settings from Work Settings
	try:
		workspace_visibilty = loads(
			frappe.db.get_single_value("Workspace Settings", "workspace_visibility_json") or "{}"
		)
	except JSONDecodeError:
		workspace_visibilty = {}

	# Filter Page based on Permission
	for page in all_pages:
		try:
			workspace = Workspace(page, True)
			if has_access or workspace.is_permitted():
				if page.public and (has_access or not page.is_hidden) and page.title != "Welcome Workspace":
					pages.append(page)
				elif page.for_user == frappe.session.user:
					private_pages.append(page)
				page["label"] = _(page.get("id"))

			if page["id"] in workspace_visibilty:
				page["visibility"] = workspace_visibilty[page["id"]]

			if not page["app"] and page["module"]:
				page["app"] = frappe.db.get_value("Module Def", page["module"], "app_name") or get_module_app(
					page["module"]
				)
			if page["link_type"] == "Report":
				report_type, ref_doctype = frappe.db.get_value(
					"Report", page["link_to"], ["report_type", "ref_doctype"]
				)
				page["report"] = {
					"report_type": report_type,
					"ref_doctype": ref_doctype,
				}

		except frappe.PermissionError:
			pass
	if private_pages:
		pages.extend(private_pages)

	if len(pages) == 0:
		pages.append(next((x for x in all_pages if x["title"] == "Welcome Workspace"), None))

	return {
		"workspace_setup_completed": frappe.db.get_single_value(
			"Workspace Settings", "workspace_setup_completed"
		),
		"pages": pages,
		"has_access": has_access,
		"has_create_access": frappe.has_permission(doctype="Workspace", ptype="create"),
	}


def get_table_with_counts():
	counts = frappe.cache.get_value("information_schema:counts")
	if not counts:
		counts = build_table_count_cache()

	return counts


def get_custom_reports_and_doctypes(module):
	return [
		_dict({"label": _("Custom Documents"), "links": get_custom_doctype_list(module)}),
		_dict({"label": _("Custom Reports"), "links": get_custom_report_list(module)}),
	]


def get_custom_doctype_list(module):
	doctypes = frappe.get_all(
		"DocType",
		fields=["id"],
		filters={"custom": 1, "istable": 0, "module": module},
		order_by="id",
	)

	return [
		{
			"type": "Link",
			"link_type": "doctype",
			"link_to": d.id,
			"label": _(d.id),
		}
		for d in doctypes
	]


def get_custom_report_list(module):
	"""Return list on new style reports for modules."""
	reports = frappe.get_all(
		"Report",
		fields=["id", "ref_doctype", "report_type"],
		filters={"is_standard": "No", "disabled": 0, "module": module},
		order_by="id",
	)

	return [
		{
			"type": "Link",
			"link_type": "report",
			"doctype": r.ref_doctype,
			"dependencies": r.ref_doctype,
			"is_query_report": 1
			if r.report_type in ("Query Report", "Script Report", "Custom Report")
			else 0,
			"label": _(r.id),
			"link_to": r.id,
			"report_ref_doctype": r.ref_doctype,
		}
		for r in reports
	]


def save_new_widget(doc, page, blocks, new_widgets):
	widgets = _dict()
	if new_widgets:
		widgets = _dict(loads(new_widgets))

		if widgets.chart:
			doc.charts.extend(new_widget(widgets.chart, "Workspace Chart", "charts"))
		if widgets.shortcut:
			doc.shortcuts.extend(new_widget(widgets.shortcut, "Workspace Shortcut", "shortcuts"))
		if widgets.quick_list:
			doc.quick_lists.extend(new_widget(widgets.quick_list, "Workspace Quick List", "quick_lists"))
		if widgets.custom_block:
			doc.custom_blocks.extend(
				new_widget(widgets.custom_block, "Workspace Custom Block", "custom_blocks")
			)
		if widgets.number_card:
			doc.number_cards.extend(new_widget(widgets.number_card, "Workspace Number Card", "number_cards"))
		if widgets.card:
			doc.build_links_table_from_card(widgets.card)

	# remove duplicate and unwanted widgets
	clean_up(doc, blocks)

	try:
		doc.save(ignore_permissions=True)
	except (ValidationError, TypeError) as e:
		# Create a json string to log
		json_config = widgets and dumps(widgets, sort_keys=True, indent=4)

		# Error log body
		log = f"""
		page: {page}
		config: {json_config}
		exception: {e}
		"""
		doc.log_error("Could not save customization", log)
		raise

	return True


def clean_up(original_page, blocks):
	page_widgets = {}

	for wid in ["shortcut", "card", "chart", "quick_list", "number_card", "custom_block"]:
		# get list of widget's name from blocks
		page_widgets[wid] = [x["data"][wid + "_id"] for x in loads(blocks) if x["type"] == wid]

	# shortcut, chart, quick_list, number_card & custom_block cleanup
	for wid in ["shortcut", "chart", "quick_list", "number_card", "custom_block"]:
		updated_widgets = []
		original_page.get(wid + "s").reverse()

		for w in original_page.get(wid + "s"):
			if w.label in page_widgets[wid] and w.label not in [x.label for x in updated_widgets]:
				updated_widgets.append(w)
		original_page.set(wid + "s", updated_widgets)

	# card cleanup
	for i, v in enumerate(original_page.links):
		if v.type == "Card Break" and v.label not in page_widgets["card"]:
			del original_page.links[i : i + v.link_count + 1]


def new_widget(config, doctype, parentfield):
	if not config:
		return []
	prepare_widget_list = []
	for idx, widget in enumerate(config):
		# Some cleanup
		widget.pop("id", None)

		# New Doc
		doc = frappe.new_doc(doctype)
		doc.update(widget)

		# Manually Set IDX
		doc.idx = idx + 1

		# Set Parent Field
		doc.parentfield = parentfield

		prepare_widget_list.append(doc)
	return prepare_widget_list


def prepare_widget(config, doctype, parentfield):
	"""Create widget child table entries with parent details.

	Args:
			config (dict): Dictionary containing widget config
			doctype (string): Doctype id of the child table
			parentfield (string): Parent field for the child table

	Return:
			TYPE: List of Document objects
	"""
	if not config:
		return []
	order = config.get("order")
	widgets = config.get("widgets")
	prepare_widget_list = []
	for idx, id in enumerate(order):
		wid_config = widgets[id].copy()
		# Some cleanup
		wid_config.pop("id", None)

		# New Doc
		doc = frappe.new_doc(doctype)
		doc.update(wid_config)

		# Manually Set IDX
		doc.idx = idx + 1

		# Set Parent Field
		doc.parentfield = parentfield

		prepare_widget_list.append(doc)
	return prepare_widget_list


@frappe.whitelist()
def update_onboarding_step(id, field, value):
	"""Update status of onboaridng step

	Args:
			id (string): ID of the doc
			field (string): field to be updated
			value: Value to be updated

	"""
	from frappe.utils.telemetry import capture

	frappe.db.set_value("Onboarding Step", id, field, value)

	capture(frappe.scrub(id), app="frappe_onboarding", properties={field: value})
