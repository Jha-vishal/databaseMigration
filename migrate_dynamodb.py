#!/usr/bin/env python3
import boto3
import os
import time
from dotenv import load_dotenv
from botocore.exceptions import ClientError

# Load credentials from .env
load_dotenv()

SRC_ACCESS_KEY = os.getenv("SRC_AWS_ACCESS_KEY_ID")
SRC_SECRET_KEY = os.getenv("SRC_AWS_SECRET_ACCESS_KEY")
SRC_REGION = os.getenv("SRC_AWS_REGION")

DEST_ACCESS_KEY = os.getenv("DEST_AWS_ACCESS_KEY_ID")
DEST_SECRET_KEY = os.getenv("DEST_AWS_SECRET_ACCESS_KEY")
DEST_REGION = os.getenv("DEST_AWS_REGION")

# Migration prefix mapping
SRC_PREFIX = "DEV-TABLE-1"
DEST_PREFIX = "PROD-TABLE-1"

# Source tables to migrate
TABLES_TO_MIGRATE = [
    "DEV-TABLE-1",
    "DEV-TABLE-2",
    "DEV-TABLE-3",
    "DEV-TABLE-4",
    "DEV-TABLE-5"
]

# Create boto3 sessions
src_session = boto3.Session(
    aws_access_key_id=SRC_ACCESS_KEY,
    aws_secret_access_key=SRC_SECRET_KEY,
    region_name=SRC_REGION
)

dest_session = boto3.Session(
    aws_access_key_id=DEST_ACCESS_KEY,
    aws_secret_access_key=DEST_SECRET_KEY,
    region_name=DEST_REGION
)

src_dynamodb = src_session.client("dynamodb")
dest_dynamodb = dest_session.client("dynamodb")


def copy_table_schema(src_table, dest_table):
    """Get source table schema and prepare params for destination table."""
    try:
        response = src_dynamodb.describe_table(TableName=src_table)
        table_desc = response['Table']

        create_params = {
            "TableName": dest_table,
            "AttributeDefinitions": table_desc["AttributeDefinitions"],
            "KeySchema": table_desc["KeySchema"],
            "BillingMode": table_desc.get("BillingModeSummary", {}).get("BillingMode", "PROVISIONED")
        }

        if create_params["BillingMode"] == "PROVISIONED":
            create_params["ProvisionedThroughput"] = {
                "ReadCapacityUnits": table_desc["ProvisionedThroughput"]["ReadCapacityUnits"],
                "WriteCapacityUnits": table_desc["ProvisionedThroughput"]["WriteCapacityUnits"]
            }

        if "GlobalSecondaryIndexes" in table_desc:
            gsis = []
            for gsi in table_desc["GlobalSecondaryIndexes"]:
                gsi_info = {
                    "IndexName": gsi["IndexName"],
                    "KeySchema": gsi["KeySchema"],
                    "Projection": gsi["Projection"]
                }
                if create_params["BillingMode"] == "PROVISIONED":
                    gsi_info["ProvisionedThroughput"] = {
                        "ReadCapacityUnits": gsi["ProvisionedThroughput"]["ReadCapacityUnits"],
                        "WriteCapacityUnits": gsi["ProvisionedThroughput"]["WriteCapacityUnits"]
                    }
                gsis.append(gsi_info)
            create_params["GlobalSecondaryIndexes"] = gsis

        return create_params

    except ClientError as e:
        print(f"Error describing table {src_table}: {e}")
        return None


def replicate_data(src_table, dest_table):
    """Copy all items from source to destination."""
    paginator = src_dynamodb.get_paginator("scan")
    for page in paginator.paginate(TableName=src_table):
        items = page.get("Items", [])
        if not items:
            continue
        write_requests = [{"PutRequest": {"Item": item}} for item in items]
        # Batch write in chunks of 25
        for i in range(0, len(write_requests), 25):
            batch_chunk = write_requests[i:i+25]
            dest_dynamodb.batch_write_item(RequestItems={dest_table: batch_chunk})


def migrate_table(src_table):
    dest_table = src_table.replace(SRC_PREFIX, DEST_PREFIX, 1)
    print(f"\nMigrating: {src_table} → {dest_table}")

    schema = copy_table_schema(src_table, dest_table)
    if not schema:
        return

    try:
        dest_dynamodb.create_table(**schema)
        print(f"Creating destination table {dest_table}...")
        waiter = dest_dynamodb.get_waiter("table_exists")
        waiter.wait(TableName=dest_table)
        print(f"Table {dest_table} created successfully.")
    except ClientError as e:
        if e.response['Error']['Code'] == 'ResourceInUseException':
            print(f"Table {dest_table} already exists. Skipping creation.")
        else:
            print(f"Error creating table {dest_table}: {e}")
            return

    replicate_data(src_table, dest_table)
    print(f"Data migration completed for {dest_table}.")


def main():
    for table in TABLES_TO_MIGRATE:
        migrate_table(table)


if __name__ == "__main__":
    main()