insert into temp_CT(def_id, doc_type, doc_id, doc_idx, complete_type, complete_id, complete_idx, complete_qty,
                        action)
    select t10.def_id, t10.doc_type, t10.doc_id, t10.doc_idx, t10.complete_doctype, t10.complete_docid,
           t10.complete_docidx, t10.complete_qty, 'D'
    from "$COMPLETE_TABLE" t10
    where t10.def_id = v_def_id and t10.complete_doctype = '$COMPLETE_QTY_DOCTYPE' and t10.complete_docid = v_doc_id
      and not exists(select 'A' from temp_CT t20 where t10.id = t20.id);