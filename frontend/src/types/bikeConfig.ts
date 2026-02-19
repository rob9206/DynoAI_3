/**
 * BikeConfig Types - Configuration for bike/vehicle setup in the Command Center
 * 
 * Used by the Setup Wizard to capture detailed bike information
 * for accurate VE table generation and tuning.
 */

export type EngineType = 'v-twin' | 'inline-4' | 'inline-2' | 'single' | 'v4' | 'other';
export type DisplacementUnit = 'cc' | 'ci';

export interface BikeConfig {
  /** Manufacturer (e.g., Harley-Davidson, Honda, Yamaha) */
  make: string;
  /** Model name (e.g., Street Glide, CBR1000RR) */
  model: string;
  /** Model year */
  year: number;
  /** Engine displacement */
  displacement: number;
  /** Displacement unit - cubic centimeters or cubic inches */
  displacementUnit: DisplacementUnit;
  /** Engine configuration */
  engineType: EngineType;
  /** Number of cylinders */
  cylinders: number;
  /** RPM operating range */
  rpmRange: {
    min: number;
    max: number;
  };
  /** MAP (Manifold Absolute Pressure) range in kPa */
  mapRange: {
    min: number;
    max: number;
  };
  /** Custom RPM bins for VE table (optional - uses defaults if not provided) */
  customRpmBins?: number[];
  /** Custom MAP bins for VE table (optional - uses defaults if not provided) */
  customMapBins?: number[];
}

export interface DynoConnectionConfig {
  /** IP address of the dyno */
  ipAddress: string;
  /** Network interface to use for JetDrive multicast */
  networkInterface: string;
  /** JetDrive UDP port (default: 22344) */
  port: number;
}

export interface SetupWizardState {
  /** Current step in the wizard */
  currentStep: 'dyno' | 'bike' | 'tune' | 'complete';
  /** Dyno connection configuration */
  dynoConfig: DynoConnectionConfig;
  /** Bike configuration */
  bikeConfig: BikeConfig;
  /** Whether dyno connection was successful */
  dynoConnected: boolean;
  /** Whether setup has been completed at least once */
  setupComplete: boolean;
}

/** Common motorcycle manufacturers */
export const BIKE_MAKES = [
  'Harley-Davidson',
  'Honda',
  'Yamaha',
  'Kawasaki',
  'Suzuki',
  'Ducati',
  'BMW',
  'Triumph',
  'Indian',
  'KTM',
  'Aprilia',
  'Other',
] as const;

/** Engine type options with display labels */
export const ENGINE_TYPES: { value: EngineType; label: string }[] = [
  { value: 'v-twin', label: 'V-Twin' },
  { value: 'inline-4', label: 'Inline-4' },
  { value: 'inline-2', label: 'Parallel Twin' },
  { value: 'v4', label: 'V4' },
  { value: 'single', label: 'Single Cylinder' },
  { value: 'other', label: 'Other' },
];

/** Default bike configuration */
export const DEFAULT_BIKE_CONFIG: BikeConfig = {
  make: 'Harley-Davidson',
  model: '',
  year: new Date().getFullYear(),
  displacement: 114,
  displacementUnit: 'ci',
  engineType: 'v-twin',
  cylinders: 2,
  rpmRange: { min: 1000, max: 6500 },
  mapRange: { min: 20, max: 110 },
};

/** Default dyno connection configuration */
export const DEFAULT_DYNO_CONFIG: DynoConnectionConfig = {
  ipAddress: '',
  networkInterface: '',
  port: 22344,
};

/** Default setup wizard state */
export const DEFAULT_SETUP_STATE: SetupWizardState = {
  currentStep: 'dyno',
  dynoConfig: DEFAULT_DYNO_CONFIG,
  bikeConfig: DEFAULT_BIKE_CONFIG,
  dynoConnected: false,
  setupComplete: false,
};

/**
 * Get default RPM range based on engine type
 */
export function getDefaultRpmRange(engineType: EngineType): { min: number; max: number } {
  switch (engineType) {
    case 'v-twin':
      return { min: 1000, max: 6500 };
    case 'inline-4':
      return { min: 2000, max: 14000 };
    case 'inline-2':
      return { min: 1500, max: 10000 };
    case 'v4':
      return { min: 2000, max: 13000 };
    case 'single':
      return { min: 1500, max: 10000 };
    default:
      return { min: 1000, max: 10000 };
  }
}

/**
 * Get default cylinder count based on engine type
 */
export function getDefaultCylinders(engineType: EngineType): number {
  switch (engineType) {
    case 'v-twin':
    case 'inline-2':
      return 2;
    case 'inline-4':
    case 'v4':
      return 4;
    case 'single':
      return 1;
    default:
      return 2;
  }
}
