# Version 4 Visualizations

### 1. Chart of sales per potion by hour

<img width="704" height="435" alt="Screenshot 2026-09-22 at 09 01 49" src="https://github.com/user-attachments/assets/6c17f189-7c3f-41eb-b551-d29391e2616d" />

```sql
SELECT transactions.created_at, ledger_entries.resource_key, SUM(ledger_entries.amount)
FROM transactions LEFT JOIN ledger_entries ON ledger_entries.transaction_id = transactions.id
WHERE ledger_entries.resource_key ILIKE '%potion%'
GROUP BY transactions.created_at, ledger_entries.resource_key
ORDER BY transactions.created_at
```

### 2. Table of all barrel types

<img width="972" height="393" alt="Screenshot 2026-09-22 at 09 04 20" src="https://github.com/user-attachments/assets/4559c623-c105-46d5-9f15-321837ded313" />

### 3. Visualizations of class/species/level vs potions

<img width="598" height="370" alt="Screenshot 2026-09-22 at 09 05 09" src="https://github.com/user-attachments/assets/eddc845b-5854-4a7f-b2bb-4bfb0925329a" />
<img width="598" height="371" alt="Screenshot 2026-09-22 at 09 05 15" src="https://github.com/user-attachments/assets/5e846589-9b25-4003-a81c-6c7d52ea288b" />
<img width="599" height="370" alt="Screenshot 2026-09-22 at 09 05 19" src="https://github.com/user-attachments/assets/95d14e8b-8908-404b-b9e2-61390d09408b" />

### 4. Additional visualization (potions over time by class/species/level)

<img width="598" height="370" alt="Screenshot 2026-09-22 at 09 06 51" src="https://github.com/user-attachments/assets/ab1f5444-b83b-405d-9165-f96d985f9405" />
<img width="599" height="371" alt="Screenshot 2026-09-22 at 09 06 58" src="https://github.com/user-attachments/assets/d1ae42ee-beda-4b4c-8bed-d8e4126905ca" />
<img width="599" height="371" alt="Screenshot 2026-09-22 at 09 07 04" src="https://github.com/user-attachments/assets/edc1993e-3834-4677-939b-d42cd0958a6e" />
