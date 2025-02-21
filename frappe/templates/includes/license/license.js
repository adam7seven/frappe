// license.js
// don't remove this line (used in test)

window.license = {};

license.bind_events = function () {
    $("#import-license").on("click", function (event) {
        event.preventDefault();
        $("#license-input").click();
        return false;
    });

    $("#license-input").on("change", function (event) {
        const file = event.target.files[0];
        if (file) {
            const reader = new FileReader();
            reader.onload = function (e) {
                const content = e.target.result;
                frappe
                    .call("frappe.app_core.import_license", { content: content })
                    .then((r) => {
                        frappe.show_alert(
                            {
                                message: __("The license import successfully"),
                                indicator: "green",
                            },
                            5
                        );
                        setTimeout(() => {
                            window.location.reload(true);
                        }, 1000);
                    })
                    .catch((e) => {
                        console.log(e);
                    });
            };
            reader.readAsText(file);
        }
    });

    $("#export-request").on("click", function (event) {
        event.preventDefault();

        frappe.call({
            method: "frappe.app_core.generate_request_content",
            callback: function (r) {
                if (r.message) {
                    const content = r.message;
                    const blob = new Blob([content], { type: "text/plain;charset=utf-8" });
                    const url = URL.createObjectURL(blob);
                    const a = document.createElement("a");
                    a.href = url;
                    a.download = "license.licr";
                    document.body.appendChild(a);
                    a.click();
                    document.body.removeChild(a);
                    URL.revokeObjectURL(url);
                }
            },
        });

        return false;
    });
};

frappe.ready(function () {
    license.bind_events();
});
