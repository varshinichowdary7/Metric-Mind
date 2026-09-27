-- Product dimension. Grain: one row per product_id.
select
    product_id,
    product,
    category
from {{ ref('stg_products') }}
