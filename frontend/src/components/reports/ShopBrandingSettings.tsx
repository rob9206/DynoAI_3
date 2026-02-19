/**
 * ShopBrandingSettings Component
 * 
 * Settings panel for configuring shop branding that appears on reports.
 */

import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import {
  Building2,
  Save,
  RefreshCw,
  CheckCircle2,
  AlertCircle,
  Loader2,
  Palette,
  Phone,
  Mail,
  Globe,
  MapPin,
  Image,
} from 'lucide-react';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Label } from '../ui/label';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../ui/card';
import {
  getShopBranding,
  updateShopBranding,
  type ShopBranding,
} from '../../api/reports';

export function ShopBrandingSettings() {
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  
  const [branding, setBranding] = useState<ShopBranding>({
    shop_name: '',
    tagline: '',
    address: '',
    phone: '',
    email: '',
    website: '',
    logo_path: null,
    primary_color: '#F59E0B',
    secondary_color: '#1F2937',
    accent_color: '#10B981',
  });

  useEffect(() => {
    loadBranding();
  }, []);

  const loadBranding = async () => {
    setLoading(true);
    setError(null);
    
    try {
      const data = await getShopBranding();
      setBranding(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load branding');
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    setSaving(true);
    setError(null);
    setSuccess(false);
    
    try {
      await updateShopBranding(branding);
      setSuccess(true);
      setTimeout(() => setSuccess(false), 3000);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save branding');
    } finally {
      setSaving(false);
    }
  };

  const updateField = (field: keyof ShopBranding, value: string) => {
    setBranding(prev => ({ ...prev, [field]: value }));
  };

  if (loading) {
    return (
      <Card className="bg-zinc-900/80 border-zinc-800">
        <CardContent className="py-12 text-center">
          <Loader2 className="w-8 h-8 mx-auto mb-3 animate-spin text-amber-500" />
          <p className="text-sm text-zinc-500">Loading branding settings...</p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="bg-zinc-900/80 border-zinc-800">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-amber-400">
          <Building2 className="w-5 h-5" />
          Shop Branding
        </CardTitle>
        <CardDescription>
          Configure your shop information that appears on customer reports
        </CardDescription>
      </CardHeader>
      
      <CardContent className="space-y-6">
        {/* Error/Success Messages */}
        {error && (
          <motion.div
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            className="bg-red-500/10 border border-red-500/30 rounded-lg p-3"
          >
            <div className="flex items-center gap-2 text-red-400 text-sm">
              <AlertCircle className="w-4 h-4" />
              <span>{error}</span>
            </div>
          </motion.div>
        )}
        
        {success && (
          <motion.div
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            className="bg-emerald-500/10 border border-emerald-500/30 rounded-lg p-3"
          >
            <div className="flex items-center gap-2 text-emerald-400 text-sm">
              <CheckCircle2 className="w-4 h-4" />
              <span>Branding saved successfully!</span>
            </div>
          </motion.div>
        )}

        {/* Shop Identity */}
        <div className="space-y-4">
          <h3 className="text-sm font-medium text-zinc-400">Shop Identity</h3>
          
          <div className="grid gap-4">
            <div>
              <Label htmlFor="shop_name" className="text-xs text-zinc-500">
                Shop Name *
              </Label>
              <Input
                id="shop_name"
                value={branding.shop_name}
                onChange={(e) => updateField('shop_name', e.target.value)}
                placeholder="Dawson Dynamics"
                className="mt-1 bg-zinc-800 border-zinc-700"
              />
            </div>
            
            <div>
              <Label htmlFor="tagline" className="text-xs text-zinc-500">
                Tagline
              </Label>
              <Input
                id="tagline"
                value={branding.tagline}
                onChange={(e) => updateField('tagline', e.target.value)}
                placeholder="Professional Harley-Davidson Dyno Tuning"
                className="mt-1 bg-zinc-800 border-zinc-700"
              />
            </div>
          </div>
        </div>

        {/* Contact Information */}
        <div className="space-y-4">
          <h3 className="text-sm font-medium text-zinc-400">Contact Information</h3>
          
          <div className="grid gap-4">
            <div>
              <Label htmlFor="address" className="text-xs text-zinc-500 flex items-center gap-1">
                <MapPin className="w-3 h-3" />
                Address
              </Label>
              <Input
                id="address"
                value={branding.address}
                onChange={(e) => updateField('address', e.target.value)}
                placeholder="123 Main Street, City, State 12345"
                className="mt-1 bg-zinc-800 border-zinc-700"
              />
            </div>
            
            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label htmlFor="phone" className="text-xs text-zinc-500 flex items-center gap-1">
                  <Phone className="w-3 h-3" />
                  Phone
                </Label>
                <Input
                  id="phone"
                  value={branding.phone}
                  onChange={(e) => updateField('phone', e.target.value)}
                  placeholder="(555) 123-4567"
                  className="mt-1 bg-zinc-800 border-zinc-700"
                />
              </div>
              
              <div>
                <Label htmlFor="email" className="text-xs text-zinc-500 flex items-center gap-1">
                  <Mail className="w-3 h-3" />
                  Email
                </Label>
                <Input
                  id="email"
                  type="email"
                  value={branding.email}
                  onChange={(e) => updateField('email', e.target.value)}
                  placeholder="shop@example.com"
                  className="mt-1 bg-zinc-800 border-zinc-700"
                />
              </div>
            </div>
            
            <div>
              <Label htmlFor="website" className="text-xs text-zinc-500 flex items-center gap-1">
                <Globe className="w-3 h-3" />
                Website
              </Label>
              <Input
                id="website"
                value={branding.website}
                onChange={(e) => updateField('website', e.target.value)}
                placeholder="www.yourshop.com"
                className="mt-1 bg-zinc-800 border-zinc-700"
              />
            </div>
          </div>
        </div>

        {/* Colors */}
        <div className="space-y-4">
          <h3 className="text-sm font-medium text-zinc-400 flex items-center gap-2">
            <Palette className="w-4 h-4" />
            Brand Colors
          </h3>
          
          <div className="grid grid-cols-3 gap-4">
            <div>
              <Label htmlFor="primary_color" className="text-xs text-zinc-500">
                Primary
              </Label>
              <div className="mt-1 flex gap-2">
                <Input
                  type="color"
                  id="primary_color"
                  value={branding.primary_color}
                  onChange={(e) => updateField('primary_color', e.target.value)}
                  className="w-12 h-10 p-1 bg-zinc-800 border-zinc-700 cursor-pointer"
                />
                <Input
                  value={branding.primary_color}
                  onChange={(e) => updateField('primary_color', e.target.value)}
                  className="flex-1 bg-zinc-800 border-zinc-700 font-mono text-sm"
                />
              </div>
            </div>
            
            <div>
              <Label htmlFor="secondary_color" className="text-xs text-zinc-500">
                Secondary
              </Label>
              <div className="mt-1 flex gap-2">
                <Input
                  type="color"
                  id="secondary_color"
                  value={branding.secondary_color}
                  onChange={(e) => updateField('secondary_color', e.target.value)}
                  className="w-12 h-10 p-1 bg-zinc-800 border-zinc-700 cursor-pointer"
                />
                <Input
                  value={branding.secondary_color}
                  onChange={(e) => updateField('secondary_color', e.target.value)}
                  className="flex-1 bg-zinc-800 border-zinc-700 font-mono text-sm"
                />
              </div>
            </div>
            
            <div>
              <Label htmlFor="accent_color" className="text-xs text-zinc-500">
                Accent
              </Label>
              <div className="mt-1 flex gap-2">
                <Input
                  type="color"
                  id="accent_color"
                  value={branding.accent_color}
                  onChange={(e) => updateField('accent_color', e.target.value)}
                  className="w-12 h-10 p-1 bg-zinc-800 border-zinc-700 cursor-pointer"
                />
                <Input
                  value={branding.accent_color}
                  onChange={(e) => updateField('accent_color', e.target.value)}
                  className="flex-1 bg-zinc-800 border-zinc-700 font-mono text-sm"
                />
              </div>
            </div>
          </div>
        </div>

        {/* Preview */}
        <div className="space-y-3">
          <h3 className="text-sm font-medium text-zinc-400">Preview</h3>
          
          <div 
            className="rounded-lg p-4"
            style={{ backgroundColor: branding.secondary_color + '20' }}
          >
            <p 
              className="font-bold text-xl"
              style={{ color: branding.primary_color }}
            >
              {branding.shop_name || 'Your Shop Name'}
            </p>
            {branding.tagline && (
              <p className="text-sm text-zinc-400 italic">{branding.tagline}</p>
            )}
            <div className="mt-3 flex gap-4 text-sm text-zinc-400">
              {branding.phone && <span>📞 {branding.phone}</span>}
              {branding.email && <span>✉️ {branding.email}</span>}
            </div>
          </div>
        </div>

        {/* Actions */}
        <div className="flex gap-3 pt-2">
          <Button
            variant="outline"
            onClick={loadBranding}
            disabled={loading || saving}
            className="flex-1"
          >
            <RefreshCw className={`w-4 h-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
            Reset
          </Button>
          <Button
            onClick={handleSave}
            disabled={loading || saving}
            className="flex-1 bg-amber-600 hover:bg-amber-500"
          >
            {saving ? (
              <>
                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                Saving...
              </>
            ) : (
              <>
                <Save className="w-4 h-4 mr-2" />
                Save Changes
              </>
            )}
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

export default ShopBrandingSettings;
