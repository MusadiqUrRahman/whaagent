#!/bin/bash

# Validation script for gateway configuration
# This validates the configuration without actually starting the gateway

set -e

echo "Testing gateway configuration validation..."

# Create a temporary configuration for validation
cat > /tmp/validate-config.yaml << EOF
api:
  host: "127.0.0.1"
  port: 8080

whatsapp:
  tenants:
    - id: "personal"
      phone: "+34611111111"
      default_agent: "developer"
      allowed_contacts:
        - "+34611111111"
    - id: "work"
      phone: "+34633333333"
      default_agent: "chef"
      allowed_contacts:
        - "+34633333333"

storage:
  base_path: "/tmp/whaagent-validate"
EOF

# Test configuration loading and validation
echo "Testing configuration loading..."
if gtimeout 5s ./integration_test_config_loader.sh /tmp/validate-config.yaml 2>/dev/null || timeout 5s ./integration_test_config_loader.sh /tmp/validate-config.yaml 2>/dev/null || ./integration_test_config_loader.sh /tmp/validate-config.yaml; then
    echo "Configuration validation passed"
else
    echo "Configuration validation failed"
    exit 1
fi

echo "Configuration validation passed"
rm -f /tmp/validate-config.yaml

exit 0