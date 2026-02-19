import { useEffect, useMemo, useRef, useState } from 'react';
import { AlertTriangle, X } from 'lucide-react';
import { cn } from '../../lib/utils';
import {
  useJetDriveLive,
  type JetDriveChannel,
  type UseJetDriveLiveReturn,
} from '../../hooks/useJetDriveLive';

type AlertType = 'knock' | 'thermal' | 'sensor_missing';

interface SafetyAlert {
  id: string;
  type: AlertType;
  message: string;
  timestamp: number;
}

interface SafetyStripProps {
  apiUrl?: string;
  live?: UseJetDriveLiveReturn;
  alerts?: SafetyAlert[];
  className?: string;
}

const KNOCK_THRESHOLD = 0.5;
const THERMAL_THRESHOLD_F = 250;
const SENSOR_MISSING_DEBOUNCE_MS = 3000;

const KNOCK_CANDIDATES = ['Knock', 'Knock Retard', 'Knock Level', 'Knock Count'];
const TEMP_CANDIDATES = ['ECT', 'Engine Temp', 'Coolant Temp', 'Cylinder Head Temp', 'CHT', 'Head Temp'];
const MAP_CANDIDATES = ['MAP', 'MAP kPa'];
const RPM_CANDIDATES = ['RPM', 'Engine RPM', 'Digital RPM 1', 'Digital RPM 2'];

function findChannel(
  channels: Record<string, JetDriveChannel>,
  candidates: string[],
): JetDriveChannel | null {
  for (const candidate of candidates) {
    const channel = channels[candidate];
    if (channel && Number.isFinite(channel.value)) {
      return channel;
    }
  }

  const lowerCandidates = candidates.map((entry) => entry.toLowerCase());
  for (const channel of Object.values(channels)) {
    const nameLower = channel.name.toLowerCase();
    if (lowerCandidates.some((entry) => nameLower.includes(entry))) {
      return channel;
    }
  }

  return null;
}

function normalizeTemp(value: number, units?: string): number {
  if (units?.toLowerCase().includes('c')) {
    return (value * 9) / 5 + 32;
  }
  return value;
}

/** Approximate cell coordinates from live RPM/MAP */
function getCellCoords(channels: Record<string, JetDriveChannel>): string {
  const rpmCh = findChannel(channels, RPM_CANDIDATES);
  const mapCh = findChannel(channels, MAP_CANDIDATES);
  if (rpmCh && mapCh) {
    return ` @ ~${Math.round(rpmCh.value)} RPM / ${Math.round(mapCh.value)} kPa`;
  }
  return '';
}

function SafetyStripContent({
  live,
  alerts: externalAlerts,
  className,
}: {
  live: UseJetDriveLiveReturn;
  alerts?: SafetyAlert[];
  className?: string;
}) {
  const [alerts, setAlerts] = useState<SafetyAlert[]>([]);
  const lastAlertRef = useRef<Record<AlertType, number>>({ knock: 0, thermal: 0, sensor_missing: 0 });
  const sensorMissingTrackerRef = useRef<Record<string, number>>({});

  const knockChannel = useMemo(
    () => findChannel(live.channels, KNOCK_CANDIDATES),
    [live.channels],
  );
  const tempChannel = useMemo(
    () => findChannel(live.channels, TEMP_CANDIDATES),
    [live.channels],
  );

  useEffect(() => {
    if (externalAlerts) {
      setAlerts(externalAlerts);
    }
  }, [externalAlerts]);

  useEffect(() => {
    if (externalAlerts) return;
    const now = Date.now();
    const cellCoords = getCellCoords(live.channels);

    // Knock detection
    if (knockChannel && knockChannel.value > KNOCK_THRESHOLD) {
      if (now - lastAlertRef.current.knock > 3000) {
        lastAlertRef.current.knock = now;
        setAlerts((prev) => [
          {
            id: `knock-${now}`,
            type: 'knock',
            message: `Knock detected (${knockChannel.value.toFixed(1)})${cellCoords}`,
            timestamp: now,
          },
          ...prev,
        ]);
      }
    }

    // Thermal warning
    if (tempChannel) {
      const tempF = normalizeTemp(tempChannel.value, tempChannel.units);
      if (tempF > THERMAL_THRESHOLD_F && now - lastAlertRef.current.thermal > 5000) {
        lastAlertRef.current.thermal = now;
        setAlerts((prev) => [
          {
            id: `thermal-${now}`,
            type: 'thermal',
            message: `Thermal warning (${Math.round(tempF)}°F)${cellCoords}`,
            timestamp: now,
          },
          ...prev,
        ]);
      }
    }

    // Sensor-missing detection: ECT and MAP
    if (live.isConnected) {
      const sensorChecks = [
        { key: 'ECT', channel: tempChannel, label: 'ECT sensor not reporting — check connection' },
        { key: 'MAP', channel: findChannel(live.channels, MAP_CANDIDATES), label: 'MAP sensor not reporting — check connection' },
      ];

      for (const check of sensorChecks) {
        if (!check.channel || !Number.isFinite(check.channel.value)) {
          const firstMissing = sensorMissingTrackerRef.current[check.key] ?? now;
          if (!sensorMissingTrackerRef.current[check.key]) {
            sensorMissingTrackerRef.current[check.key] = now;
          }
          if (now - firstMissing >= SENSOR_MISSING_DEBOUNCE_MS && now - lastAlertRef.current.sensor_missing > 10000) {
            lastAlertRef.current.sensor_missing = now;
            setAlerts((prev) => [
              {
                id: `sensor-${check.key}-${now}`,
                type: 'sensor_missing',
                message: check.label,
                timestamp: now,
              },
              ...prev,
            ]);
          }
        } else {
          delete sensorMissingTrackerRef.current[check.key];
        }
      }
    }
  }, [externalAlerts, knockChannel, tempChannel, live.channels, live.isConnected]);

  useEffect(() => {
    if (externalAlerts) return;
    const interval = setInterval(() => {
      setAlerts((prev) => prev.filter((alert) => Date.now() - alert.timestamp < 10000));
    }, 1000);
    return () => clearInterval(interval);
  }, [externalAlerts]);

  const dismissAlert = (id: string) => {
    setAlerts((prev) => prev.filter((alert) => alert.id !== id));
  };

  const visibleAlerts = alerts.slice(0, 2);
  const overflowCount = alerts.length - visibleAlerts.length;

  return (
    <div
      className={cn(
        'overflow-hidden transition-all duration-200',
        visibleAlerts.length > 0 ? 'h-8' : 'h-0',
        className,
      )}
    >
      {visibleAlerts.map((alert) => (
        <div
          key={alert.id}
          className={cn(
            'flex h-8 items-center gap-2 border-l-4 px-3 text-xs',
            alert.type === 'knock'
              ? 'bg-red-500/10 border-red-500 text-red-300'
              : 'bg-amber-500/10 border-amber-500 text-amber-300',
          )}
        >
          <AlertTriangle className="h-4 w-4 shrink-0" />
          <span className="truncate">{alert.message}</span>
          {overflowCount > 0 && alert === visibleAlerts[visibleAlerts.length - 1] && (
            <span className="ml-auto shrink-0 text-zinc-400">+{overflowCount} more</span>
          )}
          <button
            type="button"
            className="ml-auto shrink-0 text-zinc-500 hover:text-zinc-300 transition-colors"
            onClick={() => dismissAlert(alert.id)}
            aria-label="Dismiss alert"
          >
            <X className="h-3.5 w-3.5" />
          </button>
        </div>
      ))}
    </div>
  );
}

function SafetyStripWithLive({ apiUrl, alerts, className }: SafetyStripProps) {
  const live = useJetDriveLive({
    apiUrl: apiUrl ?? 'http://127.0.0.1:5001/api/jetdrive',
    autoConnect: true,
    pollInterval: 800,
    useSse: true,
  });

  return <SafetyStripContent live={live} alerts={alerts} className={className} />;
}

export function SafetyStrip({ live, apiUrl, alerts, className }: SafetyStripProps) {
  if (live) {
    return <SafetyStripContent live={live} alerts={alerts} className={className} />;
  }

  return <SafetyStripWithLive apiUrl={apiUrl} alerts={alerts} className={className} />;
}
