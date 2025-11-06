    insert into temp_MT(def_id, doc_type, doc_id, doc_Idx, vrf_value, qty, complete_qty, status)
    select v_def_id, v_doc_type, t11.id, case when v_main_doctype = v_doc_type then 0 else t11.idx end, $VRF_VALUE_FIELD,
            case when t11.$STATUS_FIELD = '$CLOSED_VALUE' then 0 else t11.$QTY_FIELD end,
            coalesce(t11.$COMPLETE_QTY_FIELD, 0) $COMPLETE_QTY_FIELD,
            case when t11.$STATUS_FIELD = '$CLOSED_VALUE' then 0 else 1 end
    from "tab$QTY_DOCTYPE" t11
            inner join "tab$MAIN_DOCTYPE" t10 on cast(t10.id as varchar(140)) = t11.parent
    where cast(t10.id as varchar(140)) = v_doc_id;