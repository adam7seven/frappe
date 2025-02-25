import frappe


def execute():
    # if current = 0, simply delete the key as it'll be recreated on first entry
    frappe.db.delete("Series", {"current": 0})

    duplicate_keys = frappe.db.sql(
        """
        SELECT id, max(current) as current
        from
            `tabSeries`
        group by
            id
        having count(id) > 1
    """,
        as_dict=True,
    )

    for row in duplicate_keys:
        frappe.db.delete("Series", {"id": row.id})
        if row.current:
            frappe.db.sql(
                "insert into `tabSeries`(`id`, `current`) values (%(id)s, %(current)s)",
                row,
            )
    frappe.db.commit()

    frappe.db.sql("ALTER table `tabSeries` ADD PRIMARY KEY IF NOT EXISTS (id)")
