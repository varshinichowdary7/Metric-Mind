-- Sales fact. Grain: one row per order.
--
-- Revenue lives here exactly once, so SUM(revenue) is never double counted.
-- Cost is split into material/shipping components (and a total) so the semantic
-- layer can express margin = revenue - cost, and the agent can decompose a
-- margin drop into its cost drivers. The per-cost-type breakdown at finer grain
-- lives in fct_order_costs.
with costs as (
    select
        order_id,
        sum(cost_amount)                                                as total_cost,
        sum(case when cost_type = 'material' then cost_amount else 0 end) as material_cost,
        sum(case when cost_type = 'shipping' then cost_amount else 0 end) as shipping_cost
    from {{ ref('stg_costs') }}
    group by order_id
)

select
    o.order_id,
    cast(strftime(o.order_date, '%Y%m%d') as integer) as date_id,
    o.geo_id,
    o.product_id,
    o.quantity,
    o.revenue,
    c.material_cost,
    c.shipping_cost,
    c.total_cost                                       as cost
from {{ ref('stg_orders') }} o
join costs c using (order_id)
