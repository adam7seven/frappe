# Copyright (c) 2025, Frappe Technologies and contributors
# For license information, please see license.txt

import os
import re
from string import Template

import frappe
from frappe import _
from frappe.model.document import Document

CACHE_QTY_LOGIC = "quantity_completion_qty_logic"
CACHE_COMPLETE_LOGIC = "quantity_completion_complete_logic"


class QuantityCompleteDefinition(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.core.doctype.quantity_complete_definition_item.quantity_complete_definition_item import (
			QuantityCompleteDefinitionItem,
		)
		from frappe.types import DF

		closed_rule: DF.Literal["0", "1", "2"]
		closed_standard: DF.Float
		closed_value: DF.Data | None
		complete_qty_field: DF.Literal[None]
		complete_table: DF.Literal["tabQcdL"]
		disabled: DF.Check
		exceed_percent: DF.Float
		items: DF.Table[QuantityCompleteDefinitionItem]
		limit_excess: DF.Check
		main_doctype: DF.Link
		mirror_table: DF.Literal["tabQcdM"]
		name: DF.Data | None
		predefined: DF.Check
		qty_doctype: DF.Literal[None]
		qty_field: DF.Literal[None]
		qty_logic: DF.Data | None
		remark: DF.SmallText | None
		status_field: DF.Literal[None]
		validation_field: DF.Literal[None]
	# end: auto-generated types

	def autoname(self):
		if not self.qty_doctype:
			frappe.throw(_("{0} 不能为空").format(_("Quantity DocType")))

		if not self.complete_qty_field:
			frappe.throw(_("{0} 不能为空").format(_("Complete Quantity Field")))

		self.id = f"{self.qty_doctype}-{self.complete_qty_field}".lower()

	def before_validate(self):
		# 将自定义对象添加到设置中,避免校验报错
		df = self.meta.get_field("mirror_table")
		df.options = f"tabQcdM\ntab{self.main_doctype} MT"

		df = self.meta.get_field("complete_table")
		df.options = f"tabQcdL\ntab{self.main_doctype} CT"

	def before_save(self):
		qty_doctype = frappe.get_meta(self.qty_doctype)
		if qty_doctype is None:
			frappe.throw(_("DocType {0} 未定义").format(self.qty_doctype))

		complete_qty_field = qty_doctype.get_field(self.complete_qty_field)
		if not complete_qty_field:
			frappe.throw(_("DocType {0} 中未定义字段 {1}").format(self.qty_doctype, self.complete_qty_field))

		self.name = f"{_(qty_doctype.name)} - {_(complete_qty_field.label)}"

		def_id = f"{self.qty_doctype} {self.complete_qty_field}"
		normal_def_id = re.sub(r"[^a-zA-Z0-9_]", "_", def_id).lower()
		self.qty_logic = f"qcd_{normal_def_id}"

		for def_item in self.items:
			def_item.complete_logic = f"qcd_{normal_def_id}_{def_item.idx:03d}"

	def on_update(self):
		self.generate_qty_logic_function()
		self.generate_qty_completion_logic_functions()
		self.refresh_qty_logic_cache()

	def generate_qty_logic_function(self):
		vrf_field = f"t10.{self.validation_field}" if self.validation_field else "''"
		if self.main_doctype == self.qty_doctype:
			part_template_content = self.get_template_content("qcd_template_part1.sql")
		else:
			part_template_content = self.get_template_content("qcd_template_part2.sql")

		sql_part_template = Template(part_template_content)
		sql_part = sql_part_template.substitute(
			{
				"MAIN_DOCTYPE": self.main_doctype,
				"QTY_DOCTYPE": self.qty_doctype,
				"QTY_FIELD": self.qty_field,
				"COMPLETE_QTY_FIELD": self.complete_qty_field,
				"STATUS_FIELD": self.status_field,
				"CLOSED_VALUE": self.closed_value,
				"VRF_VALUE_FIELD": vrf_field,
			}
		)

		template_content = self.get_template_content("qcd_template.sql")
		sql_template = Template(template_content)
		sql = sql_template.substitute(
			{
				"FUNCTION_NAME": self.qty_logic,
				"DEF_ID": self.id,
				"INSERT_TEMP_MT": sql_part,
				"MIRROR_TABLE": self.mirror_table,
			}
		)
		frappe.db.sql(sql)
		# self.save_script_file(self.qty_logic, sql)

	def generate_qty_completion_logic_functions(self):
		template_content = self.get_template_content("qcd_complete_template.sql")
		sql_template = Template(template_content)

		# 查询已有的存储过程名字
		sql = f"select t10.proname from pg_proc t10 where t10.proname like '{self.qty_logic}\\_%';"
		existing_proc_names = frappe.db.sql(sql, as_dict=1)
		existing_proc_names = [proc["proname"] for proc in existing_proc_names]

		for def_item in self.items:
			basetype_condition = ""
			if def_item.basetype_field:
				basetype_condition = f" and t11.{def_item.basetype_field} = '{self.qty_doctype}'"

			if def_item.main_doctype == def_item.qty_doctype:
				part1_template_content = self.get_template_content("qcd_complete_template_part1_1.sql")
				part2_template_content = self.get_template_content("qcd_complete_template_part2_1.sql")
			else:
				part1_template_content = self.get_template_content("qcd_complete_template_part1_2.sql")
				part2_template_content = self.get_template_content("qcd_complete_template_part2_2.sql")

			sql_part1_template = Template(part1_template_content)
			sql_part1 = sql_part1_template.substitute(
				{
					"QTY_DOCTYPE": self.qty_doctype,
					"COMPLETE_MAIN_DOCTYPE": def_item.main_doctype,
					"COMPLETE_QTY_DOCTYPE": def_item.qty_doctype,
					"COMPLETE_DOCTYPE_QTY_FIELD": def_item.qty_field,
					"BASEID_FIELD": def_item.baseid_field,
					"BASETYPE_CONDITION": basetype_condition,
				}
			)

			sql_part2_template = Template(part2_template_content)
			sql_part2 = sql_part2_template.substitute(
				{
					"COMPLETE_TABLE": self.complete_table,
					"COMPLETE_QTY_DOCTYPE": def_item.qty_doctype,
				}
			)

			sql = sql_template.substitute(
				{
					"FUNCTION_NAME": def_item.complete_logic,
					"DEF_ID": self.id,
					"DIRECTION": def_item.direction,
					"MAIN_DOCTYPE": self.main_doctype,
					"QTY_DOCTYPE": self.qty_doctype,
					"COMPLETE_QTY_DOCTYPE": def_item.qty_doctype,
					"COMPLETE_TABLE": self.complete_table,
					"MIRROR_TABLE": self.mirror_table,
					"STATUS_FIELD": self.status_field,
					"CLOSED_VALUE": self.closed_value,
					"COMPLETE_QTY_FIELD": self.complete_qty_field,
					"INSERT_TEMP_CT1": sql_part1,
					"INSERT_TEMP_CT2": sql_part2,
				}
			)

			frappe.db.sql(sql)
			# self.save_script_file(def_item.complete_logic, sql)

			if def_item.complete_logic in existing_proc_names:
				existing_proc_names.remove(def_item.complete_logic)

		for proc_name in existing_proc_names:
			sql = f"drop function {proc_name};"
			frappe.db.sql(sql)

	def get_template_content(self, filename: str):
		path = os.path.join(os.path.dirname(__file__), filename)
		with open(path) as f:
			return f.read()

	def refresh_qty_logic_cache(self):
		qty_logic_cache = frappe.cache.get_value(CACHE_QTY_LOGIC)
		if not qty_logic_cache:
			return  # 如果还没有缓存，直接返回

		if self.main_doctype not in qty_logic_cache:
			return  # 如果还没有缓存，直接返回

		qty_logic_dict = qty_logic_cache[self.main_doctype]
		qty_logic_dict[self.id] = self.qty_logic
		frappe.cache.set_value(CACHE_QTY_LOGIC, qty_logic_cache)

	def refresh_qty_completion_logic_cache(self):
		complete_logic_cache = frappe.cache.get_value(CACHE_COMPLETE_LOGIC)
		if not complete_logic_cache:
			return  # 如果还没有缓存，直接返回

		for def_item in self.items:
			if def_item.main_doctype not in complete_logic_cache:
				return  # 如果还没有缓存，直接返回

			complete_logic_dict = complete_logic_cache[def_item.main_doctype]
			complete_logic_dict[f"{self.id}_{def_item.idx}"] = def_item.complete_logic

		frappe.cache.set_value(CACHE_COMPLETE_LOGIC, complete_logic_cache)

	def save_script_file(self, logic_name, content):
		if not frappe.conf.get("developer_mode"):
			return

		module_name = frappe.get_value("DocType", self.main_doctype, "module")
		app_name = frappe.get_value("Module Def", module_name, "app_name")
		path = frappe.get_app_source_path(app_name, app_name, "install_scripts")
		os.makedirs(path, exist_ok=True)
		full_file_name = os.path.join(path, f"{logic_name}.sql")
		with open(full_file_name, "w") as f:
			f.write(content)


@frappe.whitelist()
def get_custom_mirror_table(main_doctype):
	if not main_doctype:
		return None

	if not frappe.db.exists("DocType", main_doctype):
		return None

	table_name = f"tab{main_doctype} MT"
	if table_exists(table_name):
		return table_name
	else:
		return None


@frappe.whitelist()
def get_custom_complete_table(main_doctype):
	if not main_doctype:
		return None

	if not frappe.db.exists("DocType", main_doctype):
		return None

	table_name = f"tab{main_doctype} CT"
	if table_exists(table_name):
		return table_name
	else:
		return None


@frappe.whitelist()
def generate_mirror_table(main_doctype: str):
	if not main_doctype:
		frappe.throw(_("{0} 不能为空").format(_("Main DocType")))

	if not frappe.db.exists("DocType", main_doctype):
		frappe.throw(_("DocType {0} 不存在").format(main_doctype))

	table_name = f"tab{main_doctype}M"
	if main_doctype.endswith("0"):
		table_name = f"tab{main_doctype[0, len(main_doctype) - 1]}M"
	frappe.db.sql(f"""
        create table if not exists "{table_name}"
        (
            like "tabQcdM" including indexes including defaults including constraints
        );""")

	return table_name


@frappe.whitelist()
def generate_complete_table(main_doctype: str):
	if not main_doctype:
		frappe.throw(_("{0} 不能为空").format(_("Main DocType")))

	if not frappe.db.exists("DocType", main_doctype):
		frappe.throw(_("DocType {0} 不存在").format(main_doctype))

	table_name = f"tab{main_doctype}L"
	if main_doctype.endswith("0"):
		table_name = f"tab{main_doctype[0, len(main_doctype) - 1]}L"
	frappe.db.sql(f"""
        create table if not exists "{table_name}"
        (
            like "tabQcdL" including indexes including defaults including constraints
        );""")

	return table_name


def execute_quantity_completion_in_hook(doc: Document, method="None"):
	"""执行数量完成逻辑的Hook，这个方法会在所有DocType的on_update和on_cancel事件中执行"""
	if (
		method != "on_update"
		and method != "on_cancel"
		and method != "on_submit"
		and method != "on_update_after_submit"
	):
		return

	if doc.docstatus == "1" and method == "on_update":
		return  # 已提交的单据，会在on_submit中执行逻辑，on_update时不需要执行

	execute_qty_logics_in_hook(doc)
	execute_complete_logics_in_hook(doc)


def execute_qty_logics_in_hook(doc: Document):
	"""执行数量逻辑"""
	qty_logic_dict = get_qty_logics_by_doctype(doc.doctype)
	if not qty_logic_dict:
		return

	doc.run_method("before_qty_logic")

	for qty_logic_key in qty_logic_dict:
		qty_logic = qty_logic_dict[qty_logic_key]
		sql = f"select * from {qty_logic}('{doc.id}');"
		result = frappe.db.sql(sql, as_dict=1)

		if not result:
			continue

		result = result[0]
		if result["error"] is None or result["error"] == 0:
			continue

		error_message = result["error_message"]
		if not error_message:
			error_message = "Unknown error"
		frappe.throw(_(error_message))

	doc.run_method("on_qty_logic")


def execute_complete_logics_in_hook(doc: Document):
	"""执行数量完成逻辑"""
	complete_logic_dict = get_complete_logics_by_doctype(doc.doctype)
	if not complete_logic_dict:
		return

	doc.run_method("before_complete_logic")

	for complete_logic_key in complete_logic_dict:
		complete_logic = complete_logic_dict[complete_logic_key]
		sql = f"select * from {complete_logic}('{doc.id}');"
		result = frappe.db.sql(sql, as_dict=1)

		if not result:
			continue

		result = result[0]
		if result["error"] is None or result["error"] == 0:
			continue

		error_message = result["error_message"]
		if not error_message:
			error_message = "Unknown error"
		frappe.throw(_(error_message))

	doc.run_method("on_complete_logic")


def get_qty_logics_by_doctype(doctype):
	"""根据DocType获取数量完成定义，优先从缓存中获取，如果缓存中没有，再从数据库中获取"""
	qty_logic_cache = frappe.cache.get_value(CACHE_QTY_LOGIC)
	if qty_logic_cache and doctype in qty_logic_cache:
		return qty_logic_cache[doctype]

	# 从数据库中获取数据
	defs = frappe.db.get_all(
		"Quantity Complete Definition",
		filters={"disabled": False, "main_doctype": doctype},
		fields=["id", "qty_logic"],
	)

	qty_logic_dict = {item["id"]: item["qty_logic"] for item in defs}
	if qty_logic_cache:
		qty_logic_cache[doctype] = qty_logic_dict
	else:
		qty_logic_cache = {doctype: qty_logic_dict}

	frappe.cache.set_value(CACHE_QTY_LOGIC, qty_logic_cache)
	return qty_logic_dict


def get_complete_logics_by_doctype(doctype):
	complete_logic_cache = frappe.cache.get_value(CACHE_COMPLETE_LOGIC)
	if complete_logic_cache and doctype in complete_logic_cache:
		return complete_logic_cache[doctype]

	# 从数据库中获取数据
	complete_logic_dict = {}
	result = frappe.db.sql(
		f"""
        select t10.id, t11.idx, t11.complete_logic
        from "tabQuantity Complete Definition" t10
            inner join "tabQuantity Complete Definition Item" t11 on cast(t10.id as varchar(140)) = t11.parent
        where t10.docstatus = 0 and t10.disabled = 0 and t11.main_doctype = '{doctype}'""",
		as_dict=True,
	)
	if len(result) == 0:
		return complete_logic_dict

	complete_logic_dict = {f"{item.id}_{item.idx}": item["complete_logic"] for item in result}
	if complete_logic_cache:
		complete_logic_cache[doctype] = complete_logic_dict
	else:
		complete_logic_cache = {doctype: complete_logic_dict}

	frappe.cache.set_value(CACHE_COMPLETE_LOGIC, complete_logic_cache)
	return complete_logic_dict


def table_exists(table_name):
	# 使用信息模式查询
	sql = f"select exists(select 1 from information_schema.tables where table_schema = 'public' and table_name = '{table_name}')"
	result = frappe.db.sql(sql, as_dict=True)
	return result[0].get("exists", False)
