#!/bin/bash

# Configuration loader test for validation
# This simulates the configuration loading process

set -e

CONFIG_FILE="$1"

if [ -z "$CONFIG_FILE" ]; then
    echo "Error: No configuration file provided"
    exit 1
fi

if [ ! -f "$CONFIG_FILE" ]; then
    echo "Error: Configuration file not found: $CONFIG_FILE"
    exit 1
fi

# Read and parse the configuration (simple validation)
echo "Reading configuration from: $CONFIG_FILE"

# Check if required sections exist
if ! grep -q "^api:" "$CONFIG_FILE"; then
    echo "Error: Missing 'api' section in configuration"
    exit 1
fi

if ! grep -q "^whatsapp:" "$CONFIG_FILE"; then
    echo "Error: Missing 'whatsapp' section in configuration"
    exit 1
fi

if ! grep -q "^storage:" "$CONFIG_FILE"; then
    echo "Error: Missing 'storage' section in configuration"
    exit 1
fi

# Check if tenants exist
if ! grep -q "^  tenants:" "$CONFIG_FILE"; then
    echo "Error: Missing 'tenants' section in configuration"
    exit 1
fi

# Count tenants - looking for tenant items in the list
TENANT_COUNT=$(grep -c "^    - id:" "$CONFIG_FILE" || echo "0")
if [ "$TENANT_COUNT" -eq 0 ]; then
    # Try alternative pattern
    TENANT_COUNT=$(grep -c "^  - id:" "$CONFIG_FILE" || echo "0")
fi
if [ "$TENANT_COUNT" -eq 0 ]; then
    echo "Error: No tenants found in configuration"
    exit 1
fi

echo "Configuration validation complete"
echo "Found $TENANT_COUNT tenant(s)"

# Validate each tenant has required fields
echo "Validating tenant configurations..."
TENANT_INDEX=0
while IFS= read -r line; do
    if echo "$line" | grep -q "^ *- id:"; then
        TENANT_ID=$(echo "$line" | sed 's/.*id: *"\([^"]*\)"\|.*id: *\([^ ]*\).*/\1\2/')
        echo "  Tenant $((TENANT_INDEX + 1)): $TENANT_ID"

        # Validate phone field
        if ! grep -A 10 "$line" "$CONFIG_FILE" | grep -q "phone:"; then
            echo "  Error: Tenant '$TENANT_ID' missing phone field"
            exit 1
        fi

        # Validate default_agent field
        if ! grep -A 10 "$line" "$CONFIG_FILE" | grep -q "default_agent:"; then
            echo "  Error: Tenant '$TENANT_ID' missing default_agent field"
            exit 1
        fi

        # Validate allowed_contacts field
        if ! grep -A 10 "$line" "$CONFIG_FILE" | grep -q "allowed_contacts:"; then
            echo "  Error: Tenant '$TENANT_ID' missing allowed_contacts field"
            exit 1
        fi

        TENANT_INDEX=$((TENANT_INDEX + 1))
    fi
done < "$CONFIG_FILE"

echo "All tenant configurations are valid"
echo "Configuration validation successful"