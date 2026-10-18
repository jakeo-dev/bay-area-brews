with
  thing as (
    select
      resource_key,
      transactions.day,
      SUM(ledger_entries.amount) over (
        partition by
          resource_key,
          transactions.day rows between UNBOUNDED PRECEDING
          and CURRENT row
      ) as total_for_this_potion_on_this_day
    from
      ledger_entries
      join transactions on ledger_entries.transaction_id = transactions.id
      join potion_mixtures on ledger_entries.resource_key = potion_mixtures.sku
    where
      resource_key ilike '%_0%'
      and amount < 0
    group by
      resource_key,
      transactions.day,
      ledger_entries.amount
  )
select
  resource_key,
  day,
  SUM(total_for_this_potion_on_this_day) * -1 as sales
from
  thing
group by
  resource_key,
  day