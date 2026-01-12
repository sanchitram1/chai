#!/bin/bash

set -uo pipefail

# This script sets up the database, runs migrations, and loads initial values

# Check if the 'chai' database exists, create it if it doesn't
if psql "$CHAI_DATABASE_ADMIN_URL" -tAc "SELECT 1 FROM pg_database WHERE datname='chai'" | grep -q 1
then
    echo "Database 'chai' already exists"
else
    echo "Database 'chai' does not exist, creating..."
    psql "$CHAI_DATABASE_ADMIN_URL" -f init-script.sql -a
fi

# Run migrations and load data (uses 'chai' database)
echo "Current database version: $(alembic current)"
alembic upgrade head || { echo "Migration failed"; exit 1; }

echo "Loading initial values into the database..."
psql "$CHAI_DATABASE_URL" -f load-values.sql -a

# Fetch and load SPDX licenses
echo "Fetching and loading SPDX licenses..."
if python fetch_spdx_licenses.py | psql -U postgres -h "$CHAI_DATABASE_URL" -d chai -a; then
    echo "SPDX licenses loaded successfully"
else
    echo "Warning: SPDX license loading failed, but continuing with migration"
fi

echo "Database setup and initialization complete"