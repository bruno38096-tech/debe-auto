# DEBE Search PoC

Parallel proof of concept. This code is intentionally isolated from the current DEBE Auto test flow and must not be merged into `main` until coverage, deduplication and source stability are validated.

## First validation query
BMW 330e Touring — Portugal.

## Architecture
source connectors -> normalized Vehicle -> dedup fingerprint -> future DEBE scoring -> search/alerts.

## Initial sources
1. BMW Premium Selection — first working PoC connector.
2. BMcar — dealer source / overlap check.
3. Santogal — dealer source / overlap check.
4. Carclasse — dealer source.
5. Caetano — dealer source / overlap check.
6. Standvirtual — benchmark, not the source of truth.

## Research snapshot — 2026-09-26
BMW Premium Selection exposed 10 BMW 330e Touring vehicles in the live official inventory during the research pass. The inventory included vehicles offered by Caetano, A Matoscar, BMcar, Santogal, MCoutinho/Bomcar and Auto Açoreana.

This is already useful evidence that one official manufacturer inventory can cover multiple dealer groups, reducing the number of connectors required for national coverage.

## Next
- stabilize BMW parser against HTML/structured endpoint changes;
- collect source offer IDs / detail URLs;
- build Standvirtual comparator;
- implement stronger cross-source dedup (VIN when exposed, otherwise model+year+km+price+dealer);
- add price-history snapshots and first_seen/last_seen;
- repeat with Mercedes-Benz Certified / Carclasse and VAG official inventory.
