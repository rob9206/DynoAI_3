# JetDrive Channel Key Schema

## Overview

JetDrive hardware consists of multiple **providers** (e.g., Power Core CPU, Atmospheric Probe) that broadcast channel data on the same multicast network. Each provider has its own set of channels with numeric IDs.

**Problem**: Channel IDs can collide between providers. For example, both Power Core CPU and Atmospheric Probe might have a channel ID 6 for "Humidity", but they represent different sensors with different values.

**Solution**: Use a unique **channel key** that combines provider ID, channel ID, and channel name.

## Channel Key Format

```
0xPPPP:CC:Name
```

Where:
- `PPPP` = Provider ID in hexadecimal (4 digits, zero-padded)
- `CC` = Channel ID within that provider (decimal)
- `Name` = Human-readable channel name

### Examples

| Key | Provider | Channel ID | Name |
|-----|----------|------------|------|
| `0x43FD:6:Humidity` | Power Core CPU (0x43FD) | 6 | Humidity |
| `0x43FE:6:Humidity` | Atmospheric Probe (0x43FE) | 6 | Humidity |
| `0x43FD:17:Internal Temp 1` | Power Core CPU | 17 | Internal Temp 1 |
| `0x43FE:7:Temperature 1` | Atmospheric Probe | 7 | Temperature 1 |

## API Response Format

The `/api/jetdrive/hardware/live/data` endpoint returns channels keyed by their unique channel key:

```json
{
  "capturing": true,
  "channels": {
    "0x43FD:6:Humidity": {
      "key": "0x43FD:6:Humidity",
      "provider_id": 17405,
      "id": 6,
      "name": "Humidity",
      "value": 0.0,
      "timestamp": 1234567890,
      "category": "atmospheric",
      "units": "%"
    },
    "0x43FE:6:Humidity": {
      "key": "0x43FE:6:Humidity",
      "provider_id": 17406,
      "id": 6,
      "name": "Humidity",
      "value": 12.36,
      "timestamp": 1234567891,
      "category": "atmospheric",
      "units": "%"
    }
  }
}
```

## Frontend Usage

### TypeScript Types

```typescript
interface JetDriveChannel {
    key: string;           // Unique key: "0xPPPP:CC:Name"
    name: string;          // Display name (clean)
    value: number;
    units: string;
    timestamp: number;
    providerId?: number;   // Provider ID (hex)
    id?: number;           // Channel ID within provider
    category?: ChannelCategory;
}
```

### Helper Functions

```typescript
// Parse a channel key into components
parseChannelKey("0x43FD:6:Humidity")
// Returns: { providerId: 0x43FD, channelId: 6, name: "Humidity" }

// Create a channel key from components
createChannelKey(0x43FD, 6, "Humidity")
// Returns: "0x43FD:6:Humidity"
```

### Grouping by Category

The `getChannelsByCategory()` function groups channels by their category while preserving unique keys:

```typescript
const grouped = getChannelsByCategory(channels);
// Returns:
// {
//   atmospheric: [
//     { key: "0x43FD:6:Humidity", name: "Humidity", data: {...}, config: {...} },
//     { key: "0x43FE:6:Humidity", name: "Humidity", data: {...}, config: {...} },
//   ],
//   dyno: [...],
//   ...
// }
```

## Backend Implementation

### JetDriveSample Dataclass

```python
@dataclass
class JetDriveSample:
    provider_id: int
    channel_id: int
    channel_name: str
    timestamp_ms: int
    value: float
    category: str = "misc"
    units: str = ""
    
    @property
    def channel_key(self) -> str:
        """Unique key: 0xPPPP:CC:Name"""
        return f"0x{self.provider_id:04X}:{self.channel_id}:{self.channel_name}"
```

### Provider Cache

Each provider's channels are cached separately in `_provider_cache` to avoid ID collisions:

```python
_provider_cache: dict[int, JetDriveProviderInfo] = {}
# Key: provider_id (int)
# Value: JetDriveProviderInfo with channels dict
```

## Benefits

1. **No collisions**: Channels from different providers are uniquely identified
2. **Traceable**: Easy to see which provider a channel came from
3. **Debuggable**: The key format is human-readable
4. **Backwards compatible**: Display name is still available in `name` field
5. **Sortable**: Keys can be sorted to group by provider
