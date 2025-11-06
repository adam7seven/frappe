create or replace function $FUNCTION_NAME(v_doc_id varchar(140))
    returns table
            (
                error int,
                error_message text
            )
    language plpgsql
as $$$$
declare
    v_def_id varchar(140) := '$DEF_ID'; v_doc_type varchar(140) := null; v_main_doctype varchar(140);
    v_error int := 0; v_error_message text := null;
begin
    select t10.qty_doctype, t10.main_doctype
    into v_doc_type, v_main_doctype
    from "tabQuantity Complete Definition" t10
    where t10.id = v_def_id;
    if v_doc_type is null
    then
        return query select 100 as error, '没有数量完成定义' as error_message;
        return;
    end if;

    --登记数量
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
        complete_qty numeric(21, 9) default 0 not null,--不能从单据中更新取镜像表中
        complete_count int default 0 not null,
        status char(1),
        ori_qty numeric(21, 9) default 0 not null,
        ori_complete_qty numeric(21, 9) default 0 not null,
        action char(1) default 'A' not null --行操作，A 新增，D 删除，U 更新，N 无变化
    ) on commit drop;

    --取消的单据也要处理（判断是否允许取消），complete_field为空时，complete_qty 有可能是空值
    $INSERT_TEMP_MT

    --根据现有数据判断是否更新
    update temp_MT t10
    set id = t11.id, ori_qty = t11.qty, ori_complete_qty = t11.complete_qty, complete_count = t11.complete_count,
        action = case when t10.qty = t11.qty and t10.status = t11.status then 'N' else 'U' end
    from "$MIRROR_TABLE" t11
    where t10.def_id = t11.def_id and t10.doc_type = t11.doc_type and t10.doc_id = t11.doc_id
      and coalesce(t10.vrf_value, '') = coalesce(t11.vrf_value, '');

    --不相同的数据要删除
    insert into temp_MT (id, def_id, doc_type, doc_id, doc_idx, vrf_value, qty, complete_qty, complete_count, status,
                         ori_qty, action)
    select t10.id, t10.def_id, t10.doc_type, t10.doc_id, t10.doc_idx, t10.vrf_value, 0, t10.complete_qty,
           t10.complete_count, t10.status, t10.qty, 'D'
    from "$MIRROR_TABLE" t10
    where t10.def_id = v_def_id and t10.doc_type = v_doc_type and t10.doc_id = v_doc_id
      and not exists(select 1 from temp_MT t20 where t20.id = t10.id);

    --完成状态不允许修改
    select 101 as error, '行' || cast(t10.doc_idx as varchar(10)) || '，不允许修改，状态已关闭'
    into v_error,v_error_message
    from temp_MT t10
    where t10.status = '0' and t10.ori_qty <> t10.qty;
    if v_error <> 0
    then
        return query select v_error as error, v_error_message as error_message;
        return;
    end if;

    select 102 as error, '行' || cast(t10.doc_idx as varchar(10)) || '，不允许修改完成数量（或删除行）'
    into v_error,v_error_message
    from temp_MT t10
    where t10.complete_qty is not null and t10.complete_qty <> t10.ori_complete_qty;
    if v_error <> 0
    then
        return query select v_error as error, v_error_message as error_message;
        return;
    end if;

    --清除没有变化的数据
    delete from temp_MT where action = 'N';

    --没有需要处理的数据就返回
    if not exists(select 1 from temp_MT)
    then
        return query select 0 as error, null as error_message;
        return;
    end if;

    --已经存在完成数量的行不能删除
    select 103 as error, '行' || cast(t10.doc_idx as varchar(10)) || '，不允许删除，已存在完成明细'
    into v_error,v_error_message
    from temp_MT t10
    where t10.action = 'D' and t10.complete_count > 0;
    if v_error <> 0
    then
        return query select v_error as error, v_error_message as error_message;
        return;
    end if;

    --新增的行完成数量必须为0
    select 104 as error, '行' || cast(t10.doc_idx as varchar(10)) || '，不允许新增行，完成数量必须为0'
    into v_error,v_error_message
    from temp_MT t10
    where t10.action = 'A' and coalesce(t10.complete_qty, 0) <> 0;
    if v_error <> 0
    then
        return query select v_error as error, v_error_message as error_message;
        return;
    end if;

    --数量修改，已完成不能修改，小于已完成的数量不能修改
    select 105 as error, '行' || cast(t10.doc_idx as varchar(10)) || '，不允许新增行，完成数量必须为0'
    into v_error,v_error_message
    from temp_MT t10
    where t10.action = 'A' and coalesce(t10.complete_qty, 0) <> 0;
    if v_error <> 0
    then
        return query select v_error as error, v_error_message as error_message;
        return;
    end if;

    --删除镜像行
    delete from "$MIRROR_TABLE" t10 using temp_MT t11 where t10.id = t11.id and t11.action = 'D';

    --更新镜像行
    update "$MIRROR_TABLE" t10
    set qty = t11.qty, status = t11.status, update_ts = now()
    from temp_MT t11
    where t10.id = t11.id and t11.action = 'U';

    --新增镜像行
    insert into "$MIRROR_TABLE" (def_id, doc_type, doc_id, doc_idx, vrf_value, qty, status)
    select t10.def_id, t10.doc_type, t10.doc_id, doc_idx, t10.vrf_value, t10.qty, t10.status
    from temp_MT t10
    where t10.action = 'A';

    return query select 0 as error, null as error_message;

end;
$$$$;

