create or replace function $FUNCTION_NAME(v_doc_id varchar(140))
    returns table
            (
                error int,
                error_message text
            )
    language plpgsql
as $$$$
declare
    v_def_id varchar(140) := '$DEF_ID';
    v_complete_direction int := $DIRECTION;
    v_closed_rule char(1) := 1; v_closed_standard decimal(21, 9) := 100.0;
    v_limit_excess smallint := 0; v_exceed_percent decimal(21, 9) := 0.0;
    v_affect_row_count int; v_error int := 0; v_error_message text := null; v_sql text := null;
begin
    select t10.closed_rule, t10.closed_standard, t10.limit_excess, t10.exceed_percent
    into v_closed_rule, v_closed_standard, v_limit_excess, v_exceed_percent
    from "tabQuantity Complete Definition" t10
    where t10.id = v_def_id;

	drop table if exists temp_MT;
    create temp table if not exists temp_MT
    (
        id bigint null,
        def_id varchar(140) not null,
        doc_type varchar(140) not null,
        doc_id varchar(140) not null,
        doc_idx int not null,
        vrf_value varchar(140),
        qty numeric(21, 9) default 0 not null,
        complete_qty numeric(21, 9) null,--不能从单据中更新取镜像表中
        complete_count int default 0 not null,
        status char(1),
        affected_line int null,
        action char(1) default 'A' not null --行操作，A 新增，D 删除，U 更新，N 无变化
    ) on commit drop;

	drop table if exists temp_CT;
    create temp table if not exists temp_CT
    (
        id bigint null,
        def_id varchar(140) not null,
        doc_type varchar(140) not null,
        doc_id varchar(140) not null,
        doc_idx int not null,
        complete_type varchar(140) not null,
        complete_id varchar(140) not null,
        complete_idx int not null,
        complete_qty numeric(21, 9) not null default 0,
        ori_qty numeric(21, 9) default 0 not null,
        mirror_id bigint null,
        action char(1) default 'A' not null --行操作，A 新增，D 删除，U 更新，N 无变化
    ) on commit drop;

    --取消时数量为0，但也要同步到已完成的数据中
    $INSERT_TEMP_CT1

    --更新原数量，原序号，行操作
    update temp_CT t10
    set id = t11.id,
        ori_qty = t11.complete_qty,
        action = (case when t11.complete_qty = t10.complete_qty then 'N' else 'U' end)
    from "$COMPLETE_TABLE" t11
    where t10.def_id = t11.def_id and t10.doc_type = t11.doc_type and t10.doc_id = t11.doc_id
      and t10.complete_type = t11.complete_doctype and t10.complete_id = t11.complete_docid;

    --不同的数据需要删除
    $INSERT_TEMP_CT2

    --清除没有变化的数据
    delete from temp_CT where action = 'N';

    --没有需要处理的数据就返回
    if not exists(select 1 from temp_CT) then
        return query select 0 as error, null as error_message;
        return;
    end if;

    --取出镜像数据
    insert into temp_MT(id, def_id, doc_type, doc_id, doc_idx, vrf_value, qty, complete_qty, complete_count, status)
    select t10.id, t10.def_id, t10.doc_type, t10.doc_id, t10.doc_idx, t10.vrf_value, t10.qty, t10.complete_qty,
           t10.complete_count, t10.status
    from "$MIRROR_TABLE" t10
         inner join temp_CT t11 on t10.def_id = t11.def_id and t10.doc_type = t11.doc_type and t10.doc_id = t11.doc_id;

    --镜像数据代码
    update temp_CT t10
    set mirror_id = t11.id
    from temp_MT t11
    where t10.def_id = t11.def_id and t10.doc_type = t11.doc_type and t10.doc_id = t11.doc_id;

    --没找到原数据
    select 101 as error, '行' || cast(t10.complete_idx as varchar(10)) || '，没有源数据'
    into v_error,v_error_message
    from temp_CT t10
    where coalesce(t10.mirror_id, 0) = 0;
    if v_error <> 0 then
        return query select v_error as error, v_error_message as error_message;
        return;
    end if;

    --原数据已关闭
    select 102 as error, '行' || cast(t10.complete_idx as varchar(10)) || '，源数据状态已关闭'
    into v_error,v_error_message
    from temp_CT t10
         inner join temp_MT t11 on t10.mirror_id = t11.id
    where t10.action <> 'N' and t11.status = '0';
    if v_error <> 0 then
        return query select v_error as error, v_error_message as error_message;
        return;
    end if;

    --超量检查
    update temp_MT t10
    set complete_qty = t10.complete_qty + (t11.new_qty - t11.ori_qty),
        affected_line = t11.min_idx,
        action = 'U'
    from (select t20.def_id, t20.doc_type, t20.doc_id, sum(t20.complete_qty) as new_qty, sum(t20.ori_qty) as ori_qty,
                 min(t20.complete_idx) as min_idx
          from temp_CT t20
          group by t20.def_id, t20.doc_type, t20.doc_id) t11
    where t10.def_id = t11.def_id and t10.doc_type = t11.doc_type and t10.doc_id = t11.doc_id;

    select 103 as error,
           '行' || cast(t10.affected_line as varchar(10)) || '，超数量完成，源数量：' || cast(t10.qty as varchar(20)) ||
           '，完成数量：' || cast(t10.complete_qty as varchar(20))
    into v_error,v_error_message
    from temp_MT t10
    where t10.action = 'U' and v_limit_excess = 1 and t10.complete_qty > (t10.qty * (1 + v_exceed_percent / 100));
    if v_error <> 0 then
        return query select v_error as error, v_error_message as error_message;
        return;
    end if;

    --删除完成行
    delete from "$COMPLETE_TABLE" t10 using temp_CT t11 where t10.id = t11.id and t11.action = 'D';

    --减少计数
    update temp_MT t10
    set complete_count = t10.complete_count - t11.cnt
    from (select t20.mirror_id, count(1) as cnt from temp_CT t20 where t20.action = 'D' group by t20.mirror_id) t11
    where t10.id = t11.mirror_id;

    --更新完成行
    update "$COMPLETE_TABLE" t10
    set complete_qty = t11.complete_qty,
        update_ts = now()
    from temp_CT t11
    where t10.id = t11.id and t11.action = 'U';

    --新增完成行
    insert into "$COMPLETE_TABLE"(def_id, doc_type, doc_id, doc_idx, complete_doctype, complete_docid,
                                            complete_docidx, complete_qty)
    select t10.def_id, t10.doc_type, t10.doc_id, t10.doc_idx, t10.complete_type, t10.complete_id, t10.complete_idx,
           t10.complete_qty
    from temp_CT t10
    where t10.action = 'A';

    --增加计数
    update temp_MT t10
    set complete_count = t10.complete_count + t11.cnt
    from (select t20.mirror_id, count(1) as cnt from temp_CT t20 where t20.action = 'A' group by t20.mirror_id) t11
    where t10.id = t11.mirror_id;

    --自动完成, 0 手动关闭,1 完成大于等于百分比,2未清数量小于值
    if v_closed_rule = '1' then
        update temp_MT t10 set status = '0' where (t10.complete_qty * 100.0 / t10.qty) >= v_closed_standard;
    end if;

    if v_closed_rule = '2' then
        update temp_MT t10 set status = '0' where t10.qty - t10.complete_qty <= v_closed_standard;
    end if;

    --更新完成信息
    update "$MIRROR_TABLE" t10
    set complete_qty = t11.complete_qty,
        complete_count = t11.complete_count,
        status = t11.status,
        update_ts = now()
    from temp_MT t11
    where t10.id = t11.id;

    get diagnostics v_affect_row_count = row_count;
    if v_affect_row_count > 0 then
        --回写源单数量
        update "tab$QTY_DOCTYPE" t10
        set $STATUS_FIELD = case when t11.status = '0' then '$CLOSED_VALUE' else t10.$STATUS_FIELD end,
            $COMPLETE_QTY_FIELD = t11.complete_qty
        from temp_MT t11
        where t11.doc_id = cast(t10.id as varchar(140));

        --更新源单时间戳（必须有时间戳）
        update "tab$MAIN_DOCTYPE" t10
        set modified = now()
        where exists(select 1 from temp_MT t20 where cast(t10.id as varchar(140)) = t20.doc_id);

		--查询当前反写的源单的字段是否还有完成定义，如果有的话，调用它
        select string_agg(E'
                    delete from temp_qcd_cmplt_error;
                    insert into temp_qcd_cmplt_error(error, error_message)
                    select t10.error, t10.error_message
                    from ' || t11.complete_logic || '(''' || t12.doc_id || E''') t10;
                    if exists(select ''A'' from temp_qcd_cmplt_error t10 where t10.error <> ''0'') then
                        return;
                    end if;', chr(10))
        into v_sql
        from "tabQuantity Complete Definition" t10
             inner join "tabQuantity Complete Definition Item" t11 on cast(t10.id as varchar(140)) = t11.parent,
             (
                 select distinct t20.doc_id
                 from temp_MT t20) t12
        where t10.docstatus = 0 and t10.disabled = 0 and t11.main_doctype = 'M0120' and t11.qty_doctype = 'M0120'
          and t11.qty_field = 'received_qty';

		if v_sql is not null then
            v_sql := E'
                create temporary table if not exists temp_qcd_cmplt_error(error integer, error_message text);
                do \$$\$$ begin
                    ' || v_sql || E'
                end;\$$\$$;';

            execute v_sql;

            select t10.error, t10.error_message into v_error, v_error_message from temp_qcd_cmplt_error t10;
        end if;

        return query select v_error as error, v_error_message as error_message;
        return;
    end if;

    return query select 0 as error, null as error_message;
end;
$$$$;
