SELECT potion_mixtures.sku, coalesce(COUNT(ledger_entries.amount), 0) 
FROM potion_mixtures LEFT JOIN ledger_entries ON ledger_entries.resource_key = potion_mixtures.sku
GROUP BY potion_mixtures.sku
ORDER BY COUNT(amount) DESC