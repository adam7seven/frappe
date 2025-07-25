# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and contributors
# License: MIT. See LICENSE

import json
import random

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils.user import UserPermissions


class DesktopIcon(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		_doctype: DF.Link | None
		_report: DF.Link | None
		app: DF.Data | None
		blocked: DF.Check
		category: DF.Data | None
		color: DF.Data | None
		custom: DF.Check
		description: DF.SmallText | None
		force_show: DF.Check
		hidden: DF.Check
		icon: DF.Data | None
		idx: DF.Int
		label: DF.Data | None
		link: DF.SmallText | None
		module: DF.Data | None
		reverse: DF.Check
		standard: DF.Check
		type: DF.Literal["module", "list", "link", "page", "query-report"]
	# end: auto-generated types

	def validate(self):
		if not self.label:
			self.label = self.module

	def on_trash(self):
		clear_desktop_icons_cache()


def after_doctype_insert():
	frappe.db.add_unique("Desktop Icon", ("module", "owner", "standard"))


def get_desktop_icons(user=None):
	"""Return desktop icons for user"""
	if not user:
		user = frappe.session.user

	user_icons = frappe.cache.hget("desktop_icons", user)

	if not user_icons:
		fields = [
			"module",
			"hidden",
			"label",
			"link",
			"type",
			"icon",
			"color",
			"description",
			"category",
			"_doctype",
			"_report",
			"idx",
			"force_show",
			"reverse",
			"custom",
			"standard",
			"blocked",
		]

		active_domains = frappe.get_active_domains()

		blocked_doctypes = frappe.get_all(
			"DocType",
			filters={"ifnull(restrict_to_domain, '')": ("not in", ",".join(active_domains))},
			fields=["id"],
		)

		blocked_doctypes = [d.get("id") for d in blocked_doctypes]

		standard_icons = frappe.get_all("Desktop Icon", fields=fields, filters={"standard": 1})

		standard_map = {}
		for icon in standard_icons:
			if icon._doctype in blocked_doctypes:
				icon.blocked = 1
			standard_map[icon.module] = icon

		user_icons = frappe.get_all("Desktop Icon", fields=fields, filters={"standard": 0, "owner": user})

		# update hidden property
		for icon in user_icons:
			standard_icon = standard_map.get(icon.module, None)

			if icon._doctype in blocked_doctypes:
				icon.blocked = 1

			# override properties from standard icon
			if standard_icon:
				for key in ("route", "label", "color", "icon", "link"):
					if standard_icon.get(key):
						icon[key] = standard_icon.get(key)

				if standard_icon.blocked:
					icon.hidden = 1

					# flag for modules_select dialog
					icon.hidden_in_standard = 1

				elif standard_icon.force_show:
					icon.hidden = 0

		# add missing standard icons (added via new install apps?)
		user_icon_names = [icon.module for icon in user_icons]
		for standard_icon in standard_icons:
			if standard_icon.module not in user_icon_names:
				# if blocked, hidden too!
				if standard_icon.blocked:
					standard_icon.hidden = 1
					standard_icon.hidden_in_standard = 1

				user_icons.append(standard_icon)

		user_blocked_modules = frappe.get_lazy_doc("User", user).get_blocked_modules()
		for icon in user_icons:
			if icon.module in user_blocked_modules:
				icon.hidden = 1

		# sort by idx
		user_icons.sort(key=lambda a: a.idx)

		# translate
		for d in user_icons:
			if d.label:
				d.label = _(d.label, context=d.parent)

		frappe.cache.hset("desktop_icons", user, user_icons)

	return user_icons


@frappe.whitelist()
def add_user_icon(_doctype, _report=None, label=None, link=None, type="link", standard=0):
	"""Add a new user desktop icon to the desktop"""

	if not label:
		label = _doctype or _report
	if not link:
		link = f"List/{_doctype}"

	# find if a standard icon exists
	icon_name = frappe.db.exists(
		"Desktop Icon", {"standard": standard, "link": link, "owner": frappe.session.user}
	)

	if icon_name:
		if frappe.db.get_value("Desktop Icon", icon_name, "hidden"):
			# if it is hidden, unhide it
			frappe.db.set_value("Desktop Icon", icon_name, "hidden", 0)
			clear_desktop_icons_cache()

	else:
		idx = (
			frappe.db.sql("select max(idx) from `tabDesktop Icon` where owner=%s", frappe.session.user)[0][0]
			or frappe.db.sql("select count(*) from `tabDesktop Icon` where standard=1")[0][0]
		)

		if not frappe.db.get_value("Report", _report):
			_report = None
			userdefined_icon = frappe.db.get_value(
				"DocType", _doctype, ["icon", "color", "module"], as_dict=True
			)
		else:
			userdefined_icon = frappe.db.get_value(
				"Report", _report, ["icon", "color", "module"], as_dict=True
			)

		module_icon = frappe.get_value(
			"Desktop Icon",
			{"standard": 1, "module": userdefined_icon.module},
			["id", "icon", "color", "reverse"],
			as_dict=True,
		)

		if not module_icon:
			module_icon = frappe._dict()
			opts = random.choice(palette)
			module_icon.color = opts[0]
			module_icon.reverse = 0 if (len(opts) > 1) else 1

		try:
			new_icon = frappe.get_doc(
				{
					"doctype": "Desktop Icon",
					"label": label,
					"module": label,
					"link": link,
					"type": type,
					"_doctype": _doctype,
					"_report": _report,
					"icon": userdefined_icon.icon or module_icon.icon,
					"color": userdefined_icon.color or module_icon.color,
					"reverse": module_icon.reverse,
					"idx": idx + 1,
					"custom": 1,
					"standard": standard,
				}
			).insert(ignore_permissions=True)
			clear_desktop_icons_cache()

			icon_name = new_icon.name

		except frappe.UniqueValidationError:
			frappe.throw(_("Desktop Icon already exists"))
		except Exception as e:
			raise e

	return icon_name


@frappe.whitelist()
def set_order(new_order, user=None):
	"""set new order by duplicating user icons (if user is set) or set global order"""
	if isinstance(new_order, str):
		new_order = json.loads(new_order)
	for i, module in enumerate(new_order):
		if module not in ("Explore",):
			if user:
				icon = get_user_copy(module, user)
			else:
				id = frappe.db.get_value("Desktop Icon", {"standard": 1, "module": module})
				if id:
					icon = frappe.get_doc("Desktop Icon", id)
				else:
					# standard icon missing, create one for DocType
					id = add_user_icon(module, standard=1)
					icon = frappe.get_doc("Desktop Icon", id)

			icon.db_set("idx", i)

	clear_desktop_icons_cache()


def set_desktop_icons(visible_list, ignore_duplicate=True):
	"""Resets all lists and makes only the given one standard,
	if the desktop icon does not exist and the id is a DocType, then will create
	an icon for the doctype"""

	# clear all custom only if setup is not complete
	if not frappe.is_setup_complete():
		frappe.db.delete("Desktop Icon", {"standard": 0})

	# set standard as blocked and hidden if setting first active domain
	if not frappe.flags.keep_desktop_icons:
		frappe.db.sql("update `tabDesktop Icon` set blocked=0, hidden=1 where standard=1")

	# set as visible if present, or add icon
	for module in list(visible_list):
		id = frappe.db.get_value("Desktop Icon", {"module": module})
		if id:
			frappe.db.set_value("Desktop Icon", id, "hidden", 0)
		else:
			if frappe.db.exists("DocType", module):
				try:
					add_user_icon(module, standard=1)
				except frappe.UniqueValidationError as e:
					if not ignore_duplicate:
						raise e
					else:
						visible_list.remove(module)
						frappe.clear_last_message()

	# set the order
	set_order(visible_list)

	clear_desktop_icons_cache()


def set_hidden_list(hidden_list, user=None):
	"""Sets property `hidden`=1 in **Desktop Icon** for given user.
	If user is None then it will set global values.
	It will also set the rest of the icons as shown (`hidden` = 0)"""
	if isinstance(hidden_list, str):
		hidden_list = json.loads(hidden_list)

	# set as hidden
	for module in hidden_list:
		set_hidden(module, user, 1)

	# set as seen
	for module in list(set(get_all_icons()) - set(hidden_list)):
		set_hidden(module, user, 0)

	if user:
		clear_desktop_icons_cache()
	else:
		frappe.clear_cache()


def set_hidden(module, user=None, hidden=1):
	"""Set module hidden property for given user. If user is not specified,
	hide/unhide it globally"""
	if user:
		icon = get_user_copy(module, user)

		if hidden and icon.custom:
			frappe.delete_doc(icon.doctype, icon.id, ignore_permissions=True)
			return

		# hidden by user
		icon.db_set("hidden", hidden)
	else:
		icon = frappe.get_doc("Desktop Icon", {"standard": 1, "module": module})

		# blocked is globally hidden
		icon.db_set("blocked", hidden)


def get_all_icons():
	return [d.module for d in frappe.get_all("Desktop Icon", filters={"standard": 1}, fields=["module"])]


def clear_desktop_icons_cache(user=None):
	frappe.cache.hdel("desktop_icons", user or frappe.session.user)
	frappe.cache.hdel("bootinfo", user or frappe.session.user)


def get_user_copy(module, user=None):
	"""Return user copy (Desktop Icon) of the given module. If user copy does not exist, create one.

	:param module: Name of the module
	:param user: User for which the copy is required (optional)
	"""
	if not user:
		user = frappe.session.user

	desktop_icon_name = frappe.db.get_value("Desktop Icon", {"module": module, "owner": user, "standard": 0})

	if desktop_icon_name:
		return frappe.get_doc("Desktop Icon", desktop_icon_name)
	else:
		return make_user_copy(module, user)


def make_user_copy(module, user):
	"""Insert and return the user copy of a standard Desktop Icon"""
	standard_name = frappe.db.get_value("Desktop Icon", {"module": module, "standard": 1})

	if not standard_name:
		frappe.throw(_("{0} not found").format(module), frappe.DoesNotExistError)

	original = frappe.get_doc("Desktop Icon", standard_name)

	desktop_icon = frappe.get_doc({"doctype": "Desktop Icon", "standard": 0, "owner": user, "module": module})

	for key in (
		"app",
		"label",
		"route",
		"type",
		"_doctype",
		"idx",
		"reverse",
		"force_show",
		"link",
		"icon",
		"color",
	):
		if original.get(key):
			desktop_icon.set(key, original.get(key))

	desktop_icon.insert(ignore_permissions=True)

	return desktop_icon


def sync_desktop_icons():
	"""Sync desktop icons from all apps"""
	for app in frappe.get_installed_apps():
		sync_from_app(app)


def sync_from_app(app):
	"""Sync desktop icons from app. To be called during install"""
	try:
		modules = frappe.get_attr(app + ".config.desktop.get_data")() or {}
	except ImportError:
		return []

	if isinstance(modules, dict):
		modules_list = []
		for m, desktop_icon in modules.items():
			desktop_icon["module"] = m
			modules_list.append(desktop_icon)
	else:
		modules_list = modules

	for i, m in enumerate(modules_list):
		desktop_icon_name = frappe.db.get_value(
			"Desktop Icon", {"module": m["module"], "app": app, "standard": 1}
		)
		if desktop_icon_name:
			desktop_icon = frappe.get_doc("Desktop Icon", desktop_icon_name)
		else:
			# new icon
			desktop_icon = frappe.get_doc(
				{"doctype": "Desktop Icon", "idx": i, "standard": 1, "app": app, "owner": "Administrator"}
			)

		if "doctype" in m:
			m["_doctype"] = m.pop("doctype")

		desktop_icon.update(m)
		try:
			desktop_icon.save()
		except frappe.exceptions.UniqueValidationError:
			pass

	return modules_list


@frappe.whitelist()
def update_icons(hidden_list, user=None):
	"""update modules"""
	if not user:
		frappe.only_for("System Manager")

	set_hidden_list(hidden_list, user)
	frappe.msgprint(frappe._("Updated"), indicator="green", title=_("Success"), alert=True)


def get_context(context):
	context.icons = get_user_icons(frappe.session.user)
	context.user = frappe.session.user

	if "System Manager" in frappe.get_roles():
		context.users = frappe.get_all(
			"User",
			filters={"user_type": "System User", "enabled": 1},
			fields=["id", "first_name", "last_name"],
		)


@frappe.whitelist()
def get_module_icons(user=None):
	if user != frappe.session.user:
		frappe.only_for("System Manager")

	if not user:
		icons = frappe.get_all("Desktop Icon", fields="*", filters={"standard": 1}, order_by="idx")
	else:
		frappe.cache.hdel("desktop_icons", user)
		icons = get_user_icons(user)

	for icon in icons:
		icon.value = frappe.db.escape(_(icon.label or icon.module))

	return {"icons": icons, "user": user}


def get_user_icons(user):
	"""Get user icons for module setup page"""
	user_perms = UserPermissions(user)
	user_perms.build_permissions()

	from frappe.boot import get_allowed_pages

	allowed_pages = get_allowed_pages()

	icons = []
	for icon in get_desktop_icons(user):
		add = True
		if icon.hidden_in_standard:
			add = False

		if not icon.custom:
			if icon.module == ["Help", "Settings"]:
				pass

			elif icon.type == "page" and icon.link not in allowed_pages:
				add = False

			elif icon.type == "module" and icon.module not in user_perms.allow_modules:
				add = False

		if add:
			icons.append(icon)

	return icons


palette = (
	("#FFC4C4",),
	("#FFE8CD",),
	("#FFD2C2",),
	("#FF8989",),
	("#FFD19C",),
	("#FFA685",),
	("#FF4D4D", 1),
	("#FFB868",),
	("#FF7846", 1),
	("#A83333", 1),
	("#A87945", 1),
	("#A84F2E", 1),
	("#D2D2FF",),
	("#F8D4F8",),
	("#DAC7FF",),
	("#A3A3FF",),
	("#F3AAF0",),
	("#B592FF",),
	("#7575FF", 1),
	("#EC7DEA", 1),
	("#8E58FF", 1),
	("#4D4DA8", 1),
	("#934F92", 1),
	("#5E3AA8", 1),
	("#EBF8CC",),
	("#FFD7D7",),
	("#D2F8ED",),
	("#D9F399",),
	("#FFB1B1",),
	("#A4F3DD",),
	("#C5EC63",),
	("#FF8989", 1),
	("#77ECCA",),
	("#7B933D", 1),
	("#A85B5B", 1),
	("#49937E", 1),
	("#FFFACD",),
	("#D2F1FF",),
	("#CEF6D1",),
	("#FFF69C",),
	("#A6E4FF",),
	("#9DECA2",),
	("#FFF168",),
	("#78D6FF",),
	("#6BE273",),
	("#A89F45", 1),
	("#4F8EA8", 1),
	("#428B46", 1),
)


@frappe.whitelist()
def hide(id, user=None):
	if not user:
		user = frappe.session.user

	try:
		set_hidden(id, user, hidden=1)
		clear_desktop_icons_cache()
	except Exception:
		return False

	return True
