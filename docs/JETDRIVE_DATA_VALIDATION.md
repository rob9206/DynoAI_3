# JetDrive Data Quality Validation

This document describes the data quality validation system for JetDrive channels.

## Overview

The JetDrive data validation system provides real-time monitoring and validation of data quality from JetDrive channels. It tracks:

- **Data Freshness**: Time since last sample per channel
- **Data Rate**: Samples per second per channel
- **Value Validation**: Checks for NaN, infinity, and out-of-range values
- **Frame Statistics**: Tracks dropped frames, malformed frames, and non-provider frames
- **Channel Health**: Overall health status for each channel

## API Endpoints

### Get Full Health Status

```http
GET /api/jetdrive/hardware/live/health
```

Returns comprehensive health metrics for all channels:

```json
{
  "overall_health": "healthy",
  "health_reason": "5/5 channels healthy",
  "healthy_channels": 5,
  "total_channels": 5,
  "channels": {
    "42": {
      "channel_id": 42,
      "channel_name": "Digital RPM 1",
      "health": "healthy",
      "health_reason": "OK",
      "last_value": 3500.0,
      "last_timestamp_ms": 1234567890,
      "age_seconds": 0.05,
      "samples_per_second": 20.5,
      "total_samples": 1024,
      "invalid_value_count": 0,
      "last_sample_time": 1234567890.5
    }
  },
  "frame_stats": {
    "total_frames": 1000,
    "dropped_frames": 5,
    "malformed_frames": 2,
    "non_provider_frames": 10,
    "drop_rate_percent": 0.5
  },
  "timestamp": 1234567890.5
}
```

### Get Health Summary

```http
GET /api/jetdrive/hardware/live/health/summary
```

Returns a simplified summary view:

```json
{
  "channels": [
    {
      "name": "Digital RPM 1",
      "id": 42,
      "health": "healthy",
      "value": 3500.0,
      "age_seconds": 0.05,
      "rate_hz": 20.5
    }
  ],
  "timestamp": 1234567890.5
}
```

## Health Status Values

- **healthy**: Channel is receiving valid data at expected rates
- **warning**: Channel has issues but is still functional (low rate, high rate, or occasional invalid values)
- **critical**: Channel has significant issues (many invalid values)
- **stale**: No data received in the last 5 seconds
- **invalid**: Channel is receiving too many invalid values (>10 consecutive)

## Configuration

You can configure expected value ranges for channels:

```python
from api.services.jetdrive_validation import get_validator

validator = get_validator()
validator.set_channel_range("Digital RPM 1", min_val=0.0, max_val=20000.0)
validator.set_channel_range("Horsepower", min_val=0.0, max_val=500.0)
```

## Integration

The validation system is automatically integrated into the live capture loop. When you start live capture via:

```http
POST /api/jetdrive/hardware/live/start
```

The system will:
1. Track all incoming samples
2. Calculate data rates
3. Validate values
4. Track frame statistics
5. Update health status in real-time

## Usage Examples

### Check Channel Health

```python
from api.services.jetdrive_validation import get_validator

validator = get_validator()

# Get health for specific channel
rpm_channel = validator.get_channel_health(42)
if rpm_channel:
    print(f"RPM Channel Health: {rpm_channel.health.value}")
    print(f"Data Rate: {rpm_channel.samples_per_second:.2f} Hz")
    print(f"Age: {rpm_channel.get_age_seconds(time.time()):.2f}s")

# Get all health
health = validator.get_all_health()
print(f"Overall: {health['overall_health']}")
print(f"Healthy Channels: {health['healthy_channels']}/{health['total_channels']}")
```

### Monitor Frame Drops

```python
health = validator.get_all_health()
frame_stats = health['frame_stats']

if frame_stats['drop_rate_percent'] > 1.0:
    print(f"WARNING: High frame drop rate: {frame_stats['drop_rate_percent']:.2f}%")
    print(f"Dropped: {frame_stats['dropped_frames']}/{frame_stats['total_frames']}")
```

## Thresholds

Default thresholds (can be customized when creating validator):

- **Stale Threshold**: 5.0 seconds (no data for 5s = stale)
- **Min Sample Rate**: 1.0 Hz (less than 1 Hz = warning)
- **Max Sample Rate**: 200.0 Hz (more than 200 Hz = warning)
- **Invalid Value Threshold**: 10 consecutive invalid values = invalid status

## Best Practices

1. **Monitor Health Regularly**: Poll the health endpoint every few seconds during active dyno runs
2. **Set Value Ranges**: Configure expected ranges for critical channels to catch sensor issues early
3. **Watch Frame Drops**: High drop rates (>1%) may indicate network issues
4. **Check Stale Channels**: If channels go stale, check hardware connections
5. **Validate Before Analysis**: Check overall health before running autotune analysis

## Troubleshooting

### All Channels Stale
- Check JetDrive hardware connection
- Verify network connectivity
- Check if live capture is running

### High Frame Drop Rate
- Check network congestion
- Verify multicast group configuration
- Check firewall settings

### Invalid Values
- Check sensor connections
- Verify sensor calibration
- Check for electrical interference

### Low Data Rate
- Check if provider is sending data
- Verify channel subscriptions
- Check for network issues

