-- Product reference data, typed from the raw landing table.
select
    cast(product_id as integer) as product_id,
    cast(product    as varchar) as product,
    cast(category   as varchar) as category
from {{ source('raw', 'raw_products') }}
