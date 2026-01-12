#!/usr/bin/env bash
set -e

export VARIANT="v3"
export SCRIPT_PATH=/docker-entrypoint-initdb.d/
export PGPASSWORD=postgres

psql --dbname template1 -f "$SCRIPT_PATH/scripts/db-$VARIANT.sql"

psql -U program -d cars -f "$SCRIPT_PATH/schemas/schema-3.sql"
psql -U program -d rentals -f "$SCRIPT_PATH/schemas/schema-3.sql"
psql -U program -d payments -f "$SCRIPT_PATH/schemas/schema-3.sql"

echo "Database initialization completed successfully!"
