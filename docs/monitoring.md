# Monitoring System Documentation

## Overview

The monitoring system provides comprehensive visibility into the application's health, performance, and resource usage through four main dashboards:

1. Error Tracking Dashboard
2. Resource Usage Dashboard
3. Performance Metrics Dashboard
4. System Health Dashboard

## Components

### 1. Prometheus

Prometheus is configured to scrape metrics from:
- Backend service
- Frontend service
- Transcriber service
- Node exporter (system metrics)
- cAdvisor (container metrics)
- PostgreSQL exporter
- Redis exporter
- MinIO
- Grafana

Configuration: `infrastructure/docker/prometheus/prometheus.yml`

### 2. Grafana

Grafana is configured with:
- Auto-provisioned dashboards
- Pre-configured data sources
- Alert notifications

Configuration:
- Dashboards: `infrastructure/docker/grafana/dashboards/`
- Provisioning: `infrastructure/docker/grafana/provisioning/`

### 3. Alert Manager

Handles alert notifications based on Prometheus alert rules.

Configuration: `infrastructure/docker/prometheus/rules/alerts.yml`

## Dashboards

### 1. Error Tracking Dashboard

Monitors application errors with:
- Error count by type
- Error severity distribution
- Error retry attempts
- Error recovery time

Access: `http://localhost:3000/d/error-tracking`

### 2. Resource Usage Dashboard

Monitors system resources with:
- CPU usage gauges and trends
- Memory usage gauges and trends
- Storage usage metrics
- Resource usage trends

Access: `http://localhost:3000/d/resource-usage`

### 3. Performance Metrics Dashboard

Monitors application performance with:
- Operation duration (p95)
- Success rates
- Queue sizes
- Queue latency

Access: `http://localhost:3000/d/performance-metrics`

### 4. System Health Dashboard

Monitors overall system health with:
- Service health status
- Database connections
- Query performance
- HTTP metrics

Access: `http://localhost:3000/d/system-health`

## Alert Rules

### Error Alerts

1. High Error Rate
   - Threshold: > 10 errors in 5 minutes
   - Severity: Warning
   - Duration: 2 minutes

2. Critical Error Rate
   - Threshold: > 50 errors in 5 minutes
   - Severity: Critical
   - Duration: 1 minute

### Resource Alerts

1. High CPU Usage
   - Threshold: > 80%
   - Severity: Warning
   - Duration: 5 minutes

2. High Memory Usage
   - Threshold: > 85%
   - Severity: Warning
   - Duration: 5 minutes

3. High Storage Usage
   - Threshold: > 85%
   - Severity: Warning
   - Duration: 5 minutes

### Performance Alerts

1. Slow Operations
   - Threshold: p95 > 5 seconds
   - Severity: Warning
   - Duration: 5 minutes

2. High Failure Rate
   - Threshold: > 5%
   - Severity: Warning
   - Duration: 5 minutes

3. High Queue Latency
   - Threshold: p95 > 30 seconds
   - Severity: Warning
   - Duration: 5 minutes

### System Alerts

1. Service Down
   - Condition: service unreachable
   - Severity: Critical
   - Duration: 1 minute

2. High Database Connections
   - Threshold: > 80%
   - Severity: Warning
   - Duration: 5 minutes

3. Slow Database Queries
   - Threshold: avg > 1 second
   - Severity: Warning
   - Duration: 5 minutes

## Metrics

### Error Metrics
- `transcribo_errors_total`: Total error count by type
- `transcribo_error_severity_total`: Error count by severity
- `transcribo_error_retry_count_total`: Retry attempts by error type
- `transcribo_error_recovery_time_seconds`: Error recovery time

### Resource Metrics
- `transcribo_cpu_percent`: CPU usage percentage
- `transcribo_memory_bytes`: Memory usage in bytes
- `transcribo_storage_bytes`: Storage usage in bytes

### Operation Metrics
- `transcribo_operation_duration_seconds`: Operation duration histogram
- `transcribo_operation_success_total`: Successful operations count
- `transcribo_operation_failures_total`: Failed operations count

### Queue Metrics
- `transcribo_queue_size`: Current queue size
- `transcribo_queue_latency_seconds`: Queue processing latency

### Database Metrics
- `transcribo_db_connections_used`: Active database connections
- `transcribo_db_connections_total`: Total database connections
- `transcribo_db_query_duration_seconds`: Query duration histogram

### HTTP Metrics
- `transcribo_http_requests_total`: Total HTTP requests
- `transcribo_http_response_time_seconds`: Response time histogram

## Usage

### Accessing Dashboards

1. Open Grafana: `http://localhost:3000`
2. Login with default credentials:
   - Username: admin
   - Password: admin
3. Navigate to Dashboards menu
4. Select desired dashboard

### Customizing Dashboards

1. Click gear icon in dashboard
2. Select "Edit"
3. Modify panels as needed
4. Save changes

### Configuring Alerts

1. Open Alert Rules: `http://localhost:3000/alerting/list`
2. Click "New Alert Rule"
3. Configure:
   - Query
   - Condition
   - Evaluation interval
   - Notifications

### Viewing Alerts

1. Open Alerting: `http://localhost:3000/alerting/list`
2. View:
   - Active alerts
   - Alert history
   - Alert rules

## Best Practices

1. Dashboard Organization
   - Use consistent naming conventions
   - Group related metrics together
   - Add clear descriptions to panels
   - Use appropriate visualizations for data types
   - Keep dashboards focused and uncluttered
   - Use variables for dynamic filtering

2. Alert Configuration
   - Set appropriate thresholds based on baseline metrics
   - Configure proper evaluation intervals
   - Add clear alert descriptions
   - Define actionable recovery steps
   - Use severity levels consistently
   - Avoid alert fatigue with proper thresholds

3. Metric Collection
   - Follow naming conventions
   - Use appropriate metric types
   - Add relevant labels
   - Consider cardinality
   - Monitor collection performance
   - Clean up unused metrics

4. Performance Optimization
   - Use efficient queries
   - Set appropriate scrape intervals
   - Monitor Prometheus performance
   - Clean up old data
   - Use recording rules for complex queries
   - Optimize dashboard refresh rates

5. Security
   - Use secure connections
   - Implement authentication
   - Configure proper access controls
   - Audit access logs
   - Secure sensitive metrics
   - Regular security updates

6. Maintenance
   - Regular backup of dashboards
   - Document changes
   - Test new configurations
   - Monitor system resources
   - Clean up old data
   - Update dependencies

7. Troubleshooting
   - Check data sources
   - Verify metric collection
   - Review alert history
   - Check system logs
   - Monitor resource usage
   - Test alert notifications
