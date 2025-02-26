import http
import json
import os
import uuid
from io import BytesIO

from pypdf import PdfWriter

import frappe
from frappe import _
from frappe.core.doctype.access_log.access_log import make_access_log
from frappe.translate import print_language
from frappe.utils.pdf import get_pdf

no_cache = 1

base_template_path = "www/printview.html"
standard_format = "templates/print_formats/standard.html"

from frappe.www.printview import validate_print_permission


@frappe.whitelist()
def download_multi_pdf(
    doctype: str | dict[str, list[str]],
    id: str | list[str],
    format: str | None = None,
    no_letterhead: bool = False,
    letterhead: str | None = None,
    options: str | None = None,
):
    """
    Calls _download_multi_pdf with the given parameters and returns the response
    """
    return _download_multi_pdf(doctype, id, format, no_letterhead, letterhead, options)


@frappe.whitelist()
def download_multi_pdf_async(
    doctype: str | dict[str, list[str]],
    id: str | list[str],
    format: str | None = None,
    no_letterhead: bool = False,
    letterhead: str | None = None,
    options: str | None = None,
):
    """
    Calls _download_multi_pdf with the given parameters in a background job, returns task ID
    """
    task_id = str(uuid.uuid4())
    if isinstance(doctype, dict):
        doc_count = sum([len(doctype[dt]) for dt in doctype])
    else:
        doc_count = len(json.loads(id))

    frappe.enqueue(
        _download_multi_pdf,
        doctype=doctype,
        id=id,
        task_id=task_id,
        format=format,
        no_letterhead=no_letterhead,
        letterhead=letterhead,
        options=options,
        queue="long" if doc_count > 20 else "short",
    )
    frappe.local.response["http_status_code"] = http.HTTPStatus.CREATED
    return {"task_id": task_id}


def _download_multi_pdf(
    doctype: str | dict[str, list[str]],
    id: str | list[str],
    format: str | None = None,
    no_letterhead: bool = False,
    letterhead: str | None = None,
    options: str | None = None,
    task_id: str | None = None,
):
    """Return a PDF compiled by concatenating multiple documents.

    The documents can be from a single DocType or multiple DocTypes.

    Note: The design may seem a little weird, but it  exists to ensure backward compatibility.
              The correct way to use this function is to pass a dict to doctype as described below

    NEW FUNCTIONALITY
    =================
    Parameters:
    doctype (dict):
            key (string): DocType id
            value (list): of strings of doc ids which need to be concatenated and printed
    id (string):
            id of the pdf which is generated
    format:
            Print Format to be used

    OLD FUNCTIONALITY - soon to be deprecated
    =========================================
    Parameters:
    doctype (string):
            id of the DocType to which the docs belong which need to be printed
    id (string or list):
            If string the id of the doc which needs to be printed
            If list the list of strings of doc ids which needs to be printed
    format:
            Print Format to be used

    Returns:
    Publishes a link to the PDF to the given task ID
    """
    filename = ""

    pdf_writer = PdfWriter()

    if isinstance(options, str):
        options = json.loads(options)

    if not isinstance(doctype, dict):
        result = json.loads(id)
        total_docs = len(result)
        filename = f"{doctype}_"

        # Concatenating pdf files
        for idx, ss in enumerate(result):
            try:
                pdf_writer = frappe.get_print(
                    doctype,
                    ss,
                    format,
                    as_pdf=True,
                    output=pdf_writer,
                    no_letterhead=no_letterhead,
                    letterhead=letterhead,
                    pdf_options=options,
                )
            except Exception:
                if task_id:
                    frappe.publish_realtime(task_id=task_id, message={"message": "Failed"})

            # Publish progress
            if task_id:
                frappe.publish_progress(
                    percent=(idx + 1) / total_docs * 100,
                    title=_("PDF Generation in Progress"),
                    description=_("{0}/{1} complete | Please leave this tab open until completion.").format(
                        idx + 1, total_docs
                    ),
                    task_id=task_id,
                )

        if task_id is None:
            frappe.local.response.filename = "{doctype}.pdf".format(doctype=doctype.replace(" ", "-").replace("/", "-"))

    else:
        total_docs = sum([len(doctype[dt]) for dt in doctype])
        count = 1
        for doctype_id in doctype:
            filename += f"{doctype_id}_"
            for doc_id in doctype[doctype_id]:
                try:
                    pdf_writer = frappe.get_print(
                        doctype_id,
                        doc_id,
                        format,
                        as_pdf=True,
                        output=pdf_writer,
                        no_letterhead=no_letterhead,
                        letterhead=letterhead,
                        pdf_options=options,
                    )
                except Exception:
                    if task_id:
                        frappe.publish_realtime(task_id=task_id, message="Failed")
                    frappe.log_error(
                        title="Error in Multi PDF download",
                        message=f"Permission Error on doc {doc_id} of doctype {doctype_id}",
                        reference_doctype=doctype_id,
                        reference_id=doc_id,
                    )

                count += 1

                if task_id:
                    frappe.publish_progress(
                        percent=count / total_docs * 100,
                        title=_("PDF Generation in Progress"),
                        description=_("{0}/{1} complete | Please leave this tab open until completion.").format(
                            count, total_docs
                        ),
                        task_id=task_id,
                    )
        if task_id is None:
            frappe.local.response.filename = f"{id}.pdf"

    with BytesIO() as merged_pdf:
        pdf_writer.write(merged_pdf)
        if task_id:
            _file = frappe.get_doc(
                {
                    "doctype": "File",
                    "file_name": f"{filename}{task_id}.pdf",
                    "content": merged_pdf.getvalue(),
                    "is_private": 1,
                }
            )
            _file.save()
            frappe.publish_realtime(f"task_complete:{task_id}", message={"file_url": _file.unique_url})
        else:
            frappe.local.response.filecontent = merged_pdf.getvalue()
            frappe.local.response.type = "pdf"


from frappe.deprecation_dumpster import read_multi_pdf


@frappe.whitelist(allow_guest=True)
def download_pdf(doctype: str, id: str, format=None, doc=None, no_letterhead=0, language=None, letterhead=None):
    doc = doc or frappe.get_doc(doctype, id)
    validate_print_permission(doc)

    with print_language(language):
        pdf_file = frappe.get_print(
            doctype, id, format, doc=doc, as_pdf=True, letterhead=letterhead, no_letterhead=no_letterhead
        )

    frappe.local.response.filename = "{id}.pdf".format(id=id.replace(" ", "-").replace("/", "-"))
    frappe.local.response.filecontent = pdf_file
    frappe.local.response.type = "pdf"


@frappe.whitelist()
def report_to_pdf(html, orientation="Landscape"):
    make_access_log(file_type="PDF", method="PDF", page=html)
    frappe.local.response.filename = "report.pdf"
    frappe.local.response.filecontent = get_pdf(html, {"orientation": orientation})
    frappe.local.response.type = "pdf"


@frappe.whitelist()
def print_by_server(doctype, id, printer_setting, print_format=None, doc=None, no_letterhead=0, file_path=None):
    print_settings = frappe.get_doc("Network Printer Settings", printer_setting)
    try:
        import cups
    except ImportError:
        frappe.throw(_("You need to install pycups to use this feature!"))

    try:
        cups.setServer(print_settings.server_ip)
        cups.setPort(print_settings.port)
        conn = cups.Connection()
        output = PdfWriter()
        output = frappe.get_print(
            doctype, id, print_format, doc=doc, no_letterhead=no_letterhead, as_pdf=True, output=output
        )
        if not file_path:
            file_path = os.path.join("/", "tmp", f"frappe-pdf-{frappe.generate_hash()}.pdf")
        output.write(open(file_path, "wb"))
        conn.printFile(print_settings.printer_name, file_path, id, {})
    except OSError as e:
        if (
            "ContentNotFoundError" in e.message
            or "ContentOperationNotPermittedError" in e.message
            or "UnknownContentError" in e.message
            or "RemoteHostClosedError" in e.message
        ):
            frappe.throw(_("PDF generation failed"))
    except cups.IPPError:
        frappe.throw(_("Printing failed"))
