export default {
    name: "Doctype With Child Table",
    actions: [],
    custom: 1,
    autoid: "field:title",
    creation: "2022-02-09 20:15:21.242213",
    doctype: "DocType",
    editable_grid: 1,
    engine: "InnoDB",
    fields: [
        {
            fieldname: "title",
            fieldtype: "Data",
            label: "Title",
            unique: 1
        },
        {
            fieldname: "child_table",
            fieldtype: "Table",
            label: "Child Table",
            options: "Child Table Doctype",
            reqd: 1
        },
        {
            fieldname: "child_table_1",
            fieldtype: "Table",
            label: "Child Table 1",
            options: "Child Table Doctype 1"
        }
    ],
    links: [],
    modified: "2022-02-10 12:03:12.603763",
    modified_by: "Administrator",
    module: "Custom",
    naming_rule: "By fieldname",
    owner: "Administrator",
    permissions: [
        {
            create: 1,
            delete: 1,
            email: 1,
            print: 1,
            read: 1,
            role: "System Manager",
            share: 1,
            write: 1
        }
    ],
    sort_field: "modified",
    sort_order: "ASC",
    track_changes: 1
};
