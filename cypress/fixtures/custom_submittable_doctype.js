export default {
    name: "Custom Submittable DocType",
    custom: 1,
    actions: [],
    is_submittable: 1,
    creation: "2019-12-10 06:29:07.215072",
    doctype: "DocType",
    editable_grid: 1,
    engine: "InnoDB",
    fields: [
        {
            fieldname: "enabled",
            fieldtype: "Check",
            label: "Enabled",
            allow_on_submit: 1,
            reqd: 1
        },
        {
            fieldname: "title",
            fieldtype: "Data",
            label: "title",
            reqd: 1
        },
        {
            fieldname: "description",
            fieldtype: "Text Editor",
            label: "Description"
        }
    ],
    links: [],
    modified: "2019-12-10 14:40:53.127615",
    modified_by: "Administrator",
    module: "Custom",
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
            write: 1,
            submit: 1,
            cancel: 1
        }
    ],
    quick_entry: 1,
    sort_field: "modified",
    sort_order: "ASC",
    track_changes: 1
};
