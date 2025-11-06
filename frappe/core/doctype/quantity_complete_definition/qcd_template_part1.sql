    insert into temp_MT(def_id, doc_type, doc_id, doc_idx, vrf_value, qty, complete_qty, status)
    select v_def_id, v_doc_type, t10.id, 0, $VRF_VALUE_FIELD, 
        case when t10.$STATUS_FIELD = '$CLOSED_VALUE' then 0 else t10.$QTY_FIELD end, 
            coalesce(t10.$COMPLETE_QTY_FIELD, 0) $COMPLETE_QTY_FIELD,
        case when t10.$STATUS_FIELD = '$CLOSED_VALUE' then 0 else 1 end
    from "tab$MAIN_DOCTYPE" t10
    where cast(t10.id as varchar(140)) = v_doc_id;