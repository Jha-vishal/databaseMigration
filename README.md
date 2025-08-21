# databaseMigration

A small utility script to copy DynamoDB table schemas and data from a source AWS account/region to a destination account/region.

The repository includes `migrate_dynamodb.py`, which:

- Reads AWS credentials for source and destination from a `.env` file.
- Copies table schema (attributes, key schema, provisioned throughput, GSIs when present).
- Creates destination tables (skips if already exists) and copies all items using DynamoDB scans + batch writes.

## Contents

- `migrate_dynamodb.py` — main migration script
- `requirements.txt` — Python dependencies

## Quick start

1. Install Python 3.8+ and create a virtual environment (recommended).
2. Install dependencies:

```bash
python3 -m pip install -r requirements.txt
```

3. Create a `.env` file in the project root (see example below).
4. Modify the constants in `migrate_dynamodb.py` as needed (`SRC_PREFIX`, `DEST_PREFIX`, `TABLES_TO_MIGRATE`).
5. Run the script:

```bash
python3 migrate_dynamodb.py
```

## .env example

The script uses `python-dotenv` to load credentials. Create a `.env` file with these variables:

```
SRC_AWS_ACCESS_KEY_ID=AKIA...SOURCE...
SRC_AWS_SECRET_ACCESS_KEY=secret_source
SRC_AWS_REGION=us-west-2

DEST_AWS_ACCESS_KEY_ID=AKIA...DEST...
DEST_AWS_SECRET_ACCESS_KEY=secret_dest
DEST_AWS_REGION=us-east-1
```

Use IAM credentials with appropriate permissions (see IAM section below).

## Configuration (in `migrate_dynamodb.py`)

- `SRC_PREFIX` / `DEST_PREFIX` — strings used to derive the destination table name by replacing the source prefix in each source table name.
- `TABLES_TO_MIGRATE` — list of source table names to migrate.

Example mapping in the script (defaults in the file):

- `SRC_PREFIX = "DEV-TABLE-1"`
- `DEST_PREFIX = "PROD-TABLE-1"`
- If `TABLES_TO_MIGRATE = ["DEV-TABLE-1", "DEV-TABLE-2"]` then `DEV-TABLE-1` -> `PROD-TABLE-1` and `DEV-TABLE-2` -> `PROD-TABLE-2`.

If you need a different naming pattern, change the replacement logic in `migrate_table()`.

## How it works

1. The script creates two boto3 sessions (source and destination) using credentials from the environment.
2. For each table in `TABLES_TO_MIGRATE`:
	- It calls `describe_table` on the source to build creation parameters (attribute definitions, key schema, billing mode, provisioned throughput, GSIs).
	- It attempts to create the destination table and waits until it exists. If the table exists already, creation is skipped.
	- It scans the source table and copies items in batches using `batch_write_item` (chunks of 25 items).

Notes:
- Global secondary indexes (GSIs) are carried over when present; their provisioned throughput is preserved for PROVISIONED billing mode.
- BillingMode is copied if available; if missing the script assumes `PROVISIONED`.

## IAM permissions

Minimum permissions required (source and destination credentials as applicable):

- dynamodb:DescribeTable
- dynamodb:Scan
- dynamodb:CreateTable
- dynamodb:BatchWriteItem
- dynamodb:ListTables (optional)

Grant these permissions only to the least-privileged roles/accounts necessary.

## Safety, limits and recommendations

- Large tables: Scanning and writing many items can be slow and expensive. For very large tables consider using DynamoDB Streams + AWS Data Pipeline, AWS DMS, AWS Glue, or export/import via S3.
- Provisioned throughput: Watch for throttling on both source and destination. Consider running during low-traffic windows and/or increasing provisioned capacity or using on-demand tables.
- Consistency: The script uses Scan and does not guarantee transactional consistency between source and destination. For strict consistency you must design a controlled export/import or use point-in-time exports.
- Item size and limits: BatchWriteItem supports up to 25 items or 16 MB per batch — the script batches by item count but not bytes. If you have very large items, monitor for RequestLimitExceeded errors and adjust batching logic.

## Verification

After the run:

- Verify destination tables exist and check `ItemCount` and `TableStatus` from `describe_table`.
- Use simple counts (scan + select count) on both source and destination for a spot-check. For large tables prefer sampling.

## Extending / Improvements

- Add streaming/captured changes (DynamoDB Streams) to keep tables in sync after initial copy.
- Add retries and exponential backoff for transient errors and unprocessed items returned by `batch_write_item`.
- Add CLI flags or a config file to pass table lists, prefix mappings, and concurrency options instead of editing the script.
- Use DynamoDB paginator error handling and resume tokens for long-running scans.

## Troubleshooting

- "AccessDeniedException" — check IAM permissions and the credentials in your `.env`.
- "ResourceInUseException" on create — destination table already exists (this is handled by the script and will skip creation).
- Partial writes — inspect CloudWatch or the script logs for unprocessed items; add retry logic to handle them.

## License


Copyright (c) 2025 Jha-vishal

All rights reserved. This repository and its contents are the proprietary work of the
copyright owner (Jha-vishal). No part of this code may be copied, modified, or
distributed without the prior written permission of the copyright owner.

See the included `LICENSE` file for full text.

## Contact

For changes to the script, edit `migrate_dynamodb.py` and consider adding tests or a dry-run mode before running in production.
