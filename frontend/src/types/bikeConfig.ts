/**
 * Bike configuration types shared by frontend tuning utilities.
 */

export type EngineType = 'v-twin' | 'inline-4' | 'inline-2' | 'single' | 'v4' | 'other';
export type DisplacementUnit = 'cc' | 'ci';

export interface BikeConfig {
  make: string;
  model: string;
  year: number;
  displacement: number;
  displacementUnit: DisplacementUnit;
  engineType: EngineType;
  cylinders: number;
  rpmRange: {
    min: number;
    max: number;
  };
  mapRange: {
    min: number;
    max: number;
  };
  customRpmBins?: number[];
  customMapBins?: number[];
}
