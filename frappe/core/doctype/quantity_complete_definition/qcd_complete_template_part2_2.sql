insert into temp_CT(def_id, doc_type, doc_id, doc_idx, complete_type, complete_id, complete_idx, complete_qty,
                        action)
    select t10.def_id, t10.doc_type, t10.doc_id, t10.doc_idx, t10.complete_doctype, t10.complete_docid,
           t10.complete_docidx, t10.complete_qty, 'D'
    from "$COMPLETE_TABLE" t10
        inner join "tab$COMPLETE_QTY_DOCTYPE" t11 on cast(t11.id as varchar(140)) = t10.complete_docid and t11.parent = v_doc_id
    where t10.def_id = v_def_id and t10.complete_doctype = '$COMPLETE_QTY_DOCTYPE'
      and not exists(select 'A' from temp_CT t20 where t10.id = t20.id);