    insert into temp_CT(def_id, doc_type, doc_id, doc_idx, complete_type, complete_id, complete_idx, complete_qty,
                        action)
    select v_def_id, '$QTY_DOCTYPE', t11.$BASEID_FIELD, t12.idx, '$COMPLETE_QTY_DOCTYPE', t11.id,
           t11.idx, case when t10.docstatus = 2 then 0 else (t11.$COMPLETE_DOCTYPE_QTY_FIELD * v_complete_direction) end, 'A'
    from "tab$COMPLETE_MAIN_DOCTYPE" t10
         inner join "tab$COMPLETE_QTY_DOCTYPE" t11 on cast(t10.id as varchar(140)) = t11.parent
         inner join "tab$QTY_DOCTYPE" t12 on t11.$BASEID_FIELD = cast(t12.id as varchar(140))
    where cast(t10.id as varchar(140)) = v_doc_id $BASETYPE_CONDITION;