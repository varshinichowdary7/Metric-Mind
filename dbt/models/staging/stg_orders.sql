-- One row per order: typed and cleaned from the raw landing table.
select
    cast(order_id   as bigint)  as order_id,
    cast(order_date as date)    as order_date,
    cast(geo_id     as integer) as geo_id,
    cast(product_id as integer) as product_id,
    cast(quantity   as integer) as quantity,
    cast(revenue    as double)  as revenue
from {{ source('raw', 'raw_orders') }}
