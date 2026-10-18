with
  thing as (
    select
      transactions.day,
      carts.level,
      SUM(ledger_entries.amount) over (
        partition by
          transactions.day,
          carts.level rows between UNBOUNDED PRECEDING
          and CURRENT row
      ) as total_for_this_level
    from
      ledger_entries
      join transactions on ledger_entries.transaction_id = transactions.id
      join potion_mixtures on ledger_entries.resource_key = potion_mixtures.sku
      join carts on transactions.request_id = carts.id
    where
      resource_key ilike '%_0%'
      and amount < 0
    group by
      transactions.day,
      carts.level,
      ledger_entries.amount
  )
select
  day,
  level,
  SUM(total_for_this_level) * -1 as sales
from
  thing
group by
  day,
  level