create table if not exists "tabQcdM"
(
    id bigserial primary key,
    def_id varchar(140) not null,
    doc_type varchar(140) not null,
    doc_id varchar(140) not null,
    doc_idx int not null,
    vrf_value varchar(140),
    qty numeric(21, 9) not null default 0,
    complete_qty numeric(21, 9) not null default 0,
    complete_count int not null default 0,
    status varchar(10),
    update_ts timestamptz default now()
);

create table if not exists "tabQcdL"
(
    id bigserial primary key,
    def_id varchar(140) not null,
    doc_type varchar(140) not null,
    doc_id varchar(140) not null,
    doc_idx int not null,
    complete_doctype varchar(140),
    complete_docid varchar(140),
    complete_docidx int not null,
    complete_qty numeric(21, 9) not null default 0,
    update_ts timestamptz default now()
);
