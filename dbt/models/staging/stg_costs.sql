-- One row per (order, cost_type): typed and cleaned from the raw landing table.
select
    cast(cost_id     as bigint)  as cost_id,
    cast(order_id    as bigint)  as order_id,
    cast(cost_type   as varchar) as cost_type,
    cast(cost_amount as double)  as cost_amount
from {{ source('raw', 'raw_costs') }}
