// Copyright (c) 2025, Frappe Technologies and contributors
// For license information, please see license.txt

"use strict";

frappe.ui.form.on("Quantity Complete Definition", {
    refresh: handle_on_refresh,
    main_doctype: handle_on_main_doctype_changed,
    qty_doctype: handle_on_qty_doctype_changed,
    add_mirror_table_for_current_doctype: handle_on_add_mirror_table_for_current_doctype_changed,
    add_complete_table_for_current_doctype: handle_on_add_complete_table_for_current_doctype_changed,
    modify_qty_logic: handle_on_modify_qty_logic_changed,
});

frappe.ui.form.on("Quantity Complete Definition Item", {
    main_doctype: handle_on_items_main_doctype_changed,
    qty_doctype: handle_on_items_qty_doctype_changed,
    modify_logic: handle_on_items_modify_logic_changed,
});

//#region Quantity Complete Definition Events
//#endregion
async function handle_on_refresh(frm) {
    await refresh_quantity_doctype_options(frm);
    await refresh_fields_options(frm);
    await refresh_mirror_table_options(frm);
    await refresh_complete_table_options(frm);

    if (frm.doc.items) {
        frm.doc.items.forEach(async (row) => {
            await refresh_item_quantity_doctype_options(frm, row);
            await refresh_item_fields_options(frm, row);
        });
    }

    if (!frm.doc.disabled) {
        frm.set_read_only();
    } else if (frm.doc.predefined) {
        if (!frappe.boot.developer_mode) {
            frm.set_read_only();
        }
    }

    set_change_status_button(frm);
    if (frm.doc.disabled) {
        frm.dashboard.clear_comment();
        let msg = __("当前数量完成定义已禁用，数量完成逻辑将不会执行。");
        frm.dashboard.add_comment(msg, "yellow", true);
    }
}

async function handle_on_main_doctype_changed(frm) {
    await refresh_quantity_doctype_options(frm);
}

async function handle_on_qty_doctype_changed(frm) {
    frm.set_value("qty_field", "");
    frm.set_value("complete_qty_field", "");
    frm.set_value("status_field", "");
    frm.set_value("validation_field", "");

    await refresh_fields_options(frm);
}

async function handle_on_add_mirror_table_for_current_doctype_changed(frm) {
    await generate_mirror_table(frm);
}

async function handle_on_add_complete_table_for_current_doctype_changed(frm) {
    await generate_completion_table(frm);
}

async function handle_on_modify_qty_logic_changed(frm) {
    frappe.show_alert("Please modify logic in db function", 5);
}

//#region Quantity Complete Definition Item Events
//#endregion
async function handle_on_items_main_doctype_changed(frm, cdt, cdn) {
    let row = frappe.get_doc(cdt, cdn);
    await refresh_item_quantity_doctype_options(frm, row);
}

async function handle_on_items_qty_doctype_changed(frm, cdt, cdn) {
    let row = frappe.get_doc(cdt, cdn);
    row.qty_field = "";
    row.basetype_field = "";
    row.baseid_field = "";
    row.completion_logic = "";

    frm.refresh_field("items");
    await refresh_item_fields_options(frm, row);
}

function handle_on_items_modify_logic_changed(frm, cdt, cdn) {
    frappe.show_alert("Please modify logic in db function", 5);
}

//#region Methods
//#endregion
async function refresh_quantity_doctype_options(frm) {
    if (!frm.doc.main_doctype) {
        frm.set_df_property("qty_doctype", "options", "");
        return;
    }

    let main_doctype = await frappe.db.get_doc("DocType", frm.doc.main_doctype);
    let child_doctype_ids = main_doctype.fields
        .filter((field) => field.fieldtype == "Table")
        .map((field) => field.options);
    let child_doctypes = await frappe.db.get_list("DocType", {
        fields: ["id", "name"],
        filters: {
            id: ["in", child_doctype_ids],
        },
        order_by: "id",
    });

    let options = `${frm.doc.main_doctype},${main_doctype.name}`;
    child_doctypes.forEach(async (child_doctype) => {
        options = options + "\n" + `${child_doctype.id},${child_doctype.name}`;
    });
    frm.set_df_property("qty_doctype", "options", options);
}
async function refresh_fields_options(frm) {
    if (!frm.doc.qty_doctype) {
        frm.set_df_property("qty_field", "options", "");
        frm.set_df_property("complete_qty_field", "options", "");
        frm.set_df_property("status_field", "options", "");
        frm.set_df_property("validation_field", "options", "");
        return;
    }

    let qty_doctype = await frappe.db.get_doc("DocType", frm.doc.qty_doctype);
    if (qty_doctype.fields) {
        let options = qty_doctype.fields
            .filter((field) => field.fieldtype === "Float" || field.fieldtype === "Currency")
            .map((field) => `${field.fieldname},${field.label}`)
            .join("\n");
        frm.set_df_property("qty_field", "options", options);
        frm.set_df_property("complete_qty_field", "options", options);

        options = qty_doctype.fields
            .filter((field) => !!field.label)
            .map((field) => `${field.fieldname},${field.label}`)
            .join("\n");
        frm.set_df_property("status_field", "options", options);

        options = options + "\n,"; // add blank option
        frm.set_df_property("validation_field", "options", options);
    }
}
async function refresh_mirror_table_options(frm) {
    let options = "tabQcdM";
    if (!frm.doc.main_doctype) {
        frm.set_df_property("mirror_table", "options", options);
        return;
    }

    let result = await frappe.call({
        method: "frappe.core.doctype.quantity_complete_definition.quantity_complete_definition.get_custom_mirror_table",
        args: {
            main_doctype: frm.doc.main_doctype,
        },
    });
    if (result.message) {
        options += "\ntab" + frm.doc.main_doctype + " MT";
    }
    frm.set_df_property("mirror_table", "options", options);
}
async function refresh_complete_table_options(frm) {
    let options = "tabQcdL";
    if (!frm.doc.main_doctype) {
        frm.set_df_property("complete_table", "options", options);
        return;
    }

    let result = await frappe.call({
        method: "frappe.core.doctype.quantity_complete_definition.quantity_complete_definition.get_custom_complete_table",
        args: {
            main_doctype: frm.doc.main_doctype,
        },
    });
    if (result.message) {
        options += "\ntab" + frm.doc.main_doctype + " CT";
    }
    frm.set_df_property("complete_table", "options", options);
}
async function refresh_item_quantity_doctype_options(frm, row) {
    if (!row.main_doctype) {
        frm.set_child_df_property("qty_doctype", "options", "", "items", row.id);
        return;
    }

    let main_doctype = await frappe.db.get_doc("DocType", row.main_doctype);
    let child_doctype_ids = main_doctype.fields
        .filter((field) => field.fieldtype == "Table")
        .map((field) => field.options);
    let child_doctypes = await frappe.db.get_list("DocType", {
        fields: ["id", "name"],
        filters: {
            id: ["in", child_doctype_ids],
        },
        order_by: "id",
    });

    let options = `${main_doctype.id},${main_doctype.name}`;
    child_doctypes.forEach(async (child_doctype) => {
        options = options + "\n" + `${child_doctype.id},${child_doctype.name}`;
    });
    frm.set_child_df_property("qty_doctype", "options", options, "items", row.id);
}
async function refresh_item_fields_options(frm, row) {
    if (!row.qty_doctype) {
        frm.set_child_df_property("qty_field", "options", "", "items", row.id);
        frm.set_child_df_property("basetype_field", "options", "", "items", row.id);
        frm.set_child_df_property("baseid_field", "options", "", "items", row.id);
        return;
    }

    let qty_doctype = await frappe.db.get_doc("DocType", row.qty_doctype);
    if (qty_doctype.fields) {
        let options = qty_doctype.fields
            .filter((field) => field.fieldtype === "Float" || field.fieldtype === "Currency")
            .map((field) => `${field.fieldname},${field.label}`)
            .join("\n");
        frm.set_child_df_property("qty_field", "options", options, "items", row.id);

        options = qty_doctype.fields
            .filter((field) => field.fieldtype === "Link" && field.options === "DocType")
            .map((field) => `${field.fieldname},${field.label}`)
            .join("\n");
        options = options + "\n,";
        frm.set_child_df_property("basetype_field", "options", options, "items", row.id);

        options = qty_doctype.fields
            .filter((field) => field.fieldtype === "Link" || field.fieldtype === "Dynamic Link")
            .map((field) => `${field.fieldname},${field.label}`)
            .join("\n");
        frm.set_child_df_property("baseid_field", "options", options, "items", row.id);
    }
}
async function generate_mirror_table(frm) {
    if (!frm.doc.main_doctype) {
        frappe.throw("Please select Main DocType first.");
    }

    let result = await frappe.call({
        method: "frappe.core.doctype.quantity_complete_definition.quantity_complete_definition.generate_mirror_table",
        args: {
            main_doctype: frm.doc.main_doctype,
        },
        btn: $('[data-fieldname="add_mirror_table_for_current_doctype"]'),
    });

    let new_table_name = result.message;
    let df = frm.get_docfield("mirror_table");
    let options = df.options;
    if (options) {
        let option_list = options.split("\n");
        if (!option_list.includes(new_table_name)) {
            option_list.push(new_table_name);
            options = option_list.join("\n");
        }
    } else {
        options = new_table_name;
    }
    frm.set_df_property("mirror_table", "options", options);
    frm.set_value("mirror_table", new_table_name);
}
async function generate_completion_table(frm) {
    if (!frm.doc.main_doctype) {
        frappe.throw("Please select Main DocType first.");
    }

    let result = await frappe.call({
        method: "frappe.core.doctype.quantity_complete_definition.quantity_complete_definition.generate_complete_table",
        args: {
            main_doctype: frm.doc.main_doctype,
        },
        btn: $('[data-fieldname="add_complete_table_for_current_doctype"]'),
    });

    let new_table_name = result.message;
    let df = frm.get_docfield("complete_table");
    let options = df.options;
    if (options) {
        let option_list = options.split("\n");
        if (!option_list.includes(new_table_name)) {
            option_list.push(new_table_name);
            options = option_list.join("\n");
        }
    } else {
        options = new_table_name;
    }
    frm.set_df_property("complete_table", "options", options);
    frm.set_value("complete_table", new_table_name);
}
function set_change_status_button(frm) {
    frm.remove_custom_button(__("启用"));
    frm.remove_custom_button(__("禁用"));
    if (frm.doc.disabled) {
        frm.add_custom_button(__("启用"), function () {
            frm.set_value("disabled", false);
            frm.save();
            frm.set_read_only();
        });
    } else {
        frm.add_custom_button(__("禁用"), function () {
            frm.set_value("disabled", true);
            frm.save();
        });
    }
}
