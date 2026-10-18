SELECT resource_key, date_trunc('hour', ledger_entries.created_at) AS rounded_time, amount, potion_mixtures.red_amount, potion_mixtures.green_amount, potion_mixtures.blue_amount, potion_mixtures.dark_amount,
      SUM(amount) OVER (
        PARTITION BY resource_key
        ORDER BY created_at
        ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS running_total
FROM ledger_entries
JOIN potion_mixtures ON ledger_entries.resource_key = potion_mixtures.sku
WHERE resource_key ILIKE '%_0%'
ORDER BY rounded_time
LIMIT 10000