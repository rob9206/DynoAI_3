import React, { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Label } from '@/components/ui/label';
import { Slider } from '@/components/ui/slider';
import { Input } from '@/components/ui/input';
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Loader2, Settings, CheckCircle2 } from 'lucide-react';

interface TestPlannerConstraints {
  min_rpm: number;
  max_rpm: number;
  min_map_kpa: number;
  max_map_kpa: number;
  max_pulls_per_session: number;
  preferred_test_environment: 'inertia_dyno' | 'street' | 'both';
}

interface PlannerConstraintsPanelProps {
  vehicleId?: string;
  onConstraintsUpdated?: (constraints: TestPlannerConstraints) => void;
  className?: string;
}

export function PlannerConstraintsPanel({
  vehicleId = 'default',
  onConstraintsUpdated,
  className,
}: PlannerConstraintsPanelProps): React.JSX.Element {
  const [constraints, setConstraints] = useState<TestPlannerConstraints>({
    min_rpm: 1000,
    max_rpm: 7000,
    min_map_kpa: 20,
    max_map_kpa: 100,
    max_pulls_per_session: 8,
    preferred_test_environment: 'both',
  });
  
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  
  // Load constraints on mount
  useEffect(() => {
    loadConstraints();
  }, [vehicleId]);
  
  const loadConstraints = async () => {
    setLoading(true);
    setError(null);
    
    try {
      const response = await fetch(`/api/nextgen/planner/constraints?vehicle_id=${vehicleId}`);
      
      if (!response.ok) {
        throw new Error('Failed to load constraints');
      }
      
      const data = await response.json();
      setConstraints(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load constraints');
    } finally {
      setLoading(false);
    }
  };
  
  const saveConstraints = async () => {
    setSaving(true);
    setError(null);
    setSuccess(false);
    
    try {
      const response = await fetch(`/api/nextgen/planner/constraints?vehicle_id=${vehicleId}`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(constraints),
      });
      
      if (!response.ok) {
        throw new Error('Failed to save constraints');
      }
      
      const data = await response.json();
      setSuccess(true);
      
      if (onConstraintsUpdated) {
        onConstraintsUpdated(data.constraints);
      }
      
      // Clear success message after 3 seconds
      setTimeout(() => setSuccess(false), 3000);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save constraints');
    } finally {
      setSaving(false);
    }
  };
  
  const handleRpmChange = (type: 'min' | 'max', value: number[]) => {
    setConstraints(prev => ({
      ...prev,
      [type === 'min' ? 'min_rpm' : 'max_rpm']: value[0],
    }));
  };
  
  const handleMapChange = (type: 'min' | 'max', value: number[]) => {
    setConstraints(prev => ({
      ...prev,
      [type === 'min' ? 'min_map_kpa' : 'max_map_kpa']: value[0],
    }));
  };
  
  const handleMaxPullsChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = parseInt(e.target.value, 10);
    if (!isNaN(value) && value > 0) {
      setConstraints(prev => ({ ...prev, max_pulls_per_session: value }));
    }
  };
  
  const handleEnvironmentChange = (value: string) => {
    setConstraints(prev => ({
      ...prev,
      preferred_test_environment: value as TestPlannerConstraints['preferred_test_environment'],
    }));
  };
  
  if (loading) {
    return (
      <Card className={className}>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Settings className="w-5 h-5" />
            Test Planner Constraints
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-center py-8">
            <Loader2 className="w-6 h-6 animate-spin text-gray-400" />
          </div>
        </CardContent>
      </Card>
    );
  }
  
  return (
    <Card className={className}>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Settings className="w-5 h-5" />
          Test Planner Constraints
        </CardTitle>
        <CardDescription>
          Configure practical limits for test suggestions
        </CardDescription>
      </CardHeader>
      
      <CardContent className="space-y-6">
        {error && (
          <Alert variant="destructive">
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}
        
        {success && (
          <Alert className="bg-green-50 border-green-200">
            <CheckCircle2 className="w-4 h-4 text-green-600" />
            <AlertDescription className="text-green-800">
              Constraints saved successfully
            </AlertDescription>
          </Alert>
        )}
        
        {/* RPM Range */}
        <div className="space-y-4">
          <div>
            <Label className="text-sm font-semibold">RPM Range</Label>
            <p className="text-xs text-gray-600 mt-1">
              Operating RPM limits for test suggestions
            </p>
          </div>
          
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <Label className="text-xs">Min RPM</Label>
              <span className="text-xs font-mono">{constraints.min_rpm}</span>
            </div>
            <Slider
              value={[constraints.min_rpm]}
              onValueChange={(val) => handleRpmChange('min', val)}
              min={500}
              max={3000}
              step={100}
              className="w-full"
            />
          </div>
          
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <Label className="text-xs">Max RPM</Label>
              <span className="text-xs font-mono">{constraints.max_rpm}</span>
            </div>
            <Slider
              value={[constraints.max_rpm]}
              onValueChange={(val) => handleRpmChange('max', val)}
              min={5000}
              max={8500}
              step={100}
              className="w-full"
            />
          </div>
        </div>
        
        {/* MAP Range */}
        <div className="space-y-4">
          <div>
            <Label className="text-sm font-semibold">MAP Range (kPa)</Label>
            <p className="text-xs text-gray-600 mt-1">
              Manifold pressure limits
            </p>
          </div>
          
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <Label className="text-xs">Min MAP</Label>
              <span className="text-xs font-mono">{constraints.min_map_kpa} kPa</span>
            </div>
            <Slider
              value={[constraints.min_map_kpa]}
              onValueChange={(val) => handleMapChange('min', val)}
              min={10}
              max={60}
              step={5}
              className="w-full"
            />
          </div>
          
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <Label className="text-xs">Max MAP</Label>
              <span className="text-xs font-mono">{constraints.max_map_kpa} kPa</span>
            </div>
            <Slider
              value={[constraints.max_map_kpa]}
              onValueChange={(val) => handleMapChange('max', val)}
              min={80}
              max={110}
              step={5}
              className="w-full"
            />
          </div>
        </div>
        
        {/* Max Pulls Per Session */}
        <div className="space-y-2">
          <Label className="text-sm font-semibold">Max Pulls Per Session</Label>
          <Input
            type="number"
            min={1}
            max={20}
            value={constraints.max_pulls_per_session}
            onChange={handleMaxPullsChange}
            className="w-32"
          />
          <p className="text-xs text-gray-600">
            Limit number of suggested tests
          </p>
        </div>
        
        {/* Test Environment Preference */}
        <div className="space-y-3">
          <Label className="text-sm font-semibold">Preferred Test Environment</Label>
          <RadioGroup
            value={constraints.preferred_test_environment}
            onValueChange={handleEnvironmentChange}
          >
            <div className="flex items-center space-x-2">
              <RadioGroupItem value="both" id="env-both" />
              <Label htmlFor="env-both" className="text-sm cursor-pointer">
                Both (Dyno + Street)
              </Label>
            </div>
            <div className="flex items-center space-x-2">
              <RadioGroupItem value="inertia_dyno" id="env-dyno" />
              <Label htmlFor="env-dyno" className="text-sm cursor-pointer">
                Inertia Dyno Only
              </Label>
            </div>
            <div className="flex items-center space-x-2">
              <RadioGroupItem value="street" id="env-street" />
              <Label htmlFor="env-street" className="text-sm cursor-pointer">
                Street Logging Only
              </Label>
            </div>
          </RadioGroup>
        </div>
        
        {/* Action Buttons */}
        <div className="flex gap-2 pt-4 border-t">
          <Button
            onClick={saveConstraints}
            disabled={saving}
            className="flex-1"
          >
            {saving ? (
              <>
                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                Saving...
              </>
            ) : (
              'Apply Constraints'
            )}
          </Button>
          
          <Button
            variant="outline"
            onClick={loadConstraints}
            disabled={loading}
          >
            Reset
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
