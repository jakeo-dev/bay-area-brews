SELECT resource_key, date_trunc('hour', ledger_entries.created_at - INTERVAL '7 hours') AS pdt_time,
      SUM(amount) OVER (
        PARTITION BY resource_key
        ORDER BY created_at
        ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS running_total
FROM ledger_entries
WHERE resource_key ILIKE '%_ml%'
GROUP BY created_at, resource_key, amount
ORDER BY created_at DESC