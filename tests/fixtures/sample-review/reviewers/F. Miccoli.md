# Sensor Interface Requirements

## 3.2.1 Timeouts

The acquisition timeout shall be configurable by the operator. {COMM|type=technical|sev=major: the timeout must have an upper bound to avoid an unbounded wait}

## 3.3 Logging

All measurements are written to disk in CSV format. {SUGG: "disk" -> "the configured store"}
