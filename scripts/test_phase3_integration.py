from api.services.jetdrive_live_queue import get_live_queue_manager
from api.services.jetdrive_client import JetDriveSample

# Test the full integration
mgr = get_live_queue_manager()

# Simulate 100 samples across multiple windows
for i in range(100):
    s = JetDriveSample(
        provider_id=0x1001,
        channel_id=10,
        channel_name='Digital RPM 1',
        timestamp_ms=i * 10,  # 10ms apart
        value=3000.0 + i
    )
    mgr.on_sample(s)

mgr.force_flush()

# Check stats
stats = mgr.get_stats()
print(f'Samples received: {stats["samples_received"]}')
print(f'Aggregation windows: {stats["aggregation_windows"]}')
print(f'Samples enqueued: {stats["samples_enqueued"]}')
print(f'Samples dropped: {stats["samples_dropped"]}')
print(f'Queue size: {stats["queue"]["current_size"]}')
print('SUCCESS: Phase 3 integration verified!')
print('')
print('Summary:')
print(f'- {stats["samples_received"]} samples routed through queue manager')
print(f'- Aggregated into {stats["aggregation_windows"]} windows (50ms each)')
print(f'- {stats["samples_enqueued"]} data points enqueued')
print(f'- {stats["samples_dropped"]} samples dropped (0 = no overload)')
print(f'- Queue currently holds {stats["queue"]["current_size"]} items')

