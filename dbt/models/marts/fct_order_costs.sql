-- Cost fact. Grain: one row per (order, cost_type).
--
-- This exposes cost_type (material / shipping) as a real dimension, so the
-- MetricMind agent can drill "cost by cost_type" to explain a margin move.
-- Do NOT sum revenue against this table — revenue lives in fct_sales.
select
    c.cost_id,
    c.order_id,
    cast(strftime(o.order_date, '%Y%m%d') as integer) as date_id,
    o.geo_id,
    o.product_id,
    c.cost_type,
    c.cost_amount
from {{ ref('stg_costs') }} c
join {{ ref('stg_orders') }} o using (order_id)
