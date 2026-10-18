SELECT amount, date_trunc('hour', created_at) AS rounded_time
FROM ledger_entries
WHERE resource_key = 'gold' AND date_trunc('hour', created_at) >= '2026-09-30 20:00:00+00'
GROUP BY amount, rounded_time
ORDER BY rounded_time
LIMIT 10000