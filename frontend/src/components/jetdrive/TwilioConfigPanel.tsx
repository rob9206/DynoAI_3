import { useState, useEffect } from 'react';
import { MessageSquare, Save, Send, AlertCircle, CheckCircle2 } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription, CardFooter } from '../ui/card';
import { Label } from '../ui/label';
import { Input } from '../ui/input';
import { Button } from '../ui/button';
import { Switch } from '../ui/switch';
import { Alert, AlertDescription, AlertTitle } from '../ui/alert';

interface TwilioConfig {
    account_sid: string;
    auth_token: string;
    from_number: string;
    alert_to: string;
    enabled: boolean;
}

export function TwilioConfigPanel() {
    const [config, setConfig] = useState<TwilioConfig>({
        account_sid: '',
        auth_token: '',
        from_number: '',
        alert_to: '',
        enabled: true
    });
    const [isLoading, setIsLoading] = useState(true);
    const [isSaving, setIsSaving] = useState(false);
    const [isTesting, setIsTesting] = useState(false);
    const [saveStatus, setSaveStatus] = useState<'idle' | 'success' | 'error'>('idle');
    const [testResult, setTestResult] = useState<{ success: boolean; message: string } | null>(null);

    useEffect(() => {
        const fetchConfig = async () => {
            try {
                const response = await fetch('/api/notifications/twilio/config');
                if (response.ok) {
                    const data = await response.json();
                    setConfig(data);
                }
            } catch (error) {
                console.error('Failed to fetch Twilio config:', error);
            } finally {
                setIsLoading(false);
            }
        };
        fetchConfig();
    }, []);

    const handleSave = async () => {
        setIsSaving(true);
        setSaveStatus('idle');
        setTestResult(null);
        try {
            const response = await fetch('/api/notifications/twilio/config', {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(config),
            });
            if (response.ok) {
                setSaveStatus('success');
                setTimeout(() => setSaveStatus('idle'), 3000);
            } else {
                setSaveStatus('error');
            }
        } catch (error) {
            console.error('Failed to save Twilio config:', error);
            setSaveStatus('error');
        } finally {
            setIsSaving(false);
        }
    };

    const handleTest = async () => {
        setIsTesting(true);
        setTestResult(null);
        try {
            const response = await fetch('/api/notifications/twilio/test', {
                method: 'POST',
            });
            const data = await response.json();
            if (response.ok) {
                setTestResult({ success: true, message: `SMS sent successfully! SID: ${data.sid}` });
            } else {
                setTestResult({ success: false, message: data.error || 'Failed to send test SMS' });
            }
        } catch (error: any) {
            console.error('Failed to send test SMS:', error);
            setTestResult({ success: false, message: error.message || 'Network error' });
        } finally {
            setIsTesting(false);
        }
    };

    if (isLoading) {
        return <div className="p-4 text-sm text-zinc-400">Loading configuration...</div>;
    }

    return (
        <Card className="bg-zinc-900/60 border-zinc-800">
            <CardHeader className="pb-3">
                <CardTitle className="text-sm flex items-center gap-2">
                    <MessageSquare className="w-4 h-4 text-blue-400" />
                    SMS Notifications
                </CardTitle>
                <CardDescription className="text-xs">
                    Configure Twilio to receive SMS alerts when dyno runs complete or fail.
                </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
                <div className="flex items-center justify-between mb-4">
                    <div className="space-y-0.5">
                        <Label className="text-sm text-zinc-200">Enable SMS Alerts</Label>
                        <p className="text-xs text-zinc-500">
                            Send messages to the configured recipient
                        </p>
                    </div>
                    <Switch
                        checked={config.enabled}
                        onCheckedChange={(checked) => setConfig({ ...config, enabled: checked })}
                    />
                </div>

                <div className="space-y-2">
                    <Label className="text-xs text-zinc-400">Account SID</Label>
                    <Input
                        value={config.account_sid}
                        onChange={(e) => setConfig({ ...config, account_sid: e.target.value })}
                        className="h-9 bg-zinc-900/60 border-zinc-800 text-sm font-mono"
                        placeholder="ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
                    />
                </div>

                <div className="space-y-2">
                    <Label className="text-xs text-zinc-400">Auth Token</Label>
                    <Input
                        type="password"
                        value={config.auth_token}
                        onChange={(e) => setConfig({ ...config, auth_token: e.target.value })}
                        className="h-9 bg-zinc-900/60 border-zinc-800 text-sm font-mono"
                        placeholder="••••••••••••••••"
                    />
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    <div className="space-y-2">
                        <Label className="text-xs text-zinc-400">From Number</Label>
                        <Input
                            value={config.from_number}
                            onChange={(e) => setConfig({ ...config, from_number: e.target.value })}
                            className="h-9 bg-zinc-900/60 border-zinc-800 text-sm font-mono"
                            placeholder="+15005550006"
                        />
                        <p className="text-[10px] text-zinc-600">Your Twilio number (E.164)</p>
                    </div>

                    <div className="space-y-2">
                        <Label className="text-xs text-zinc-400">Alert To Number</Label>
                        <Input
                            value={config.alert_to}
                            onChange={(e) => setConfig({ ...config, alert_to: e.target.value })}
                            className="h-9 bg-zinc-900/60 border-zinc-800 text-sm font-mono"
                            placeholder="+15551234567"
                        />
                        <p className="text-[10px] text-zinc-600">Recipient number (E.164)</p>
                    </div>
                </div>

                {testResult && (
                    <Alert className={`mt-4 ${testResult.success ? 'bg-green-500/10 border-green-500/30' : 'bg-red-500/10 border-red-500/30'}`}>
                        {testResult.success ? <CheckCircle2 className="h-4 w-4 text-green-400" /> : <AlertCircle className="h-4 w-4 text-red-400" />}
                        <AlertTitle className={`text-xs font-semibold ${testResult.success ? 'text-green-400' : 'text-red-400'}`}>
                            {testResult.success ? 'Success' : 'Error'}
                        </AlertTitle>
                        <AlertDescription className={`text-xs ${testResult.success ? 'text-green-300' : 'text-red-300'}`}>
                            {testResult.message}
                        </AlertDescription>
                    </Alert>
                )}
            </CardContent>
            <CardFooter className="flex justify-between border-t border-zinc-800/50 pt-4">
                <Button
                    variant="outline"
                    size="sm"
                    onClick={handleTest}
                    disabled={isTesting || !config.account_sid || !config.alert_to || !config.from_number}
                    className="text-xs border-zinc-700 hover:bg-zinc-800"
                >
                    {isTesting ? 'Sending...' : 'Send Test SMS'}
                    {!isTesting && <Send className="w-3 h-3 ml-2" />}
                </Button>
                <Button
                    size="sm"
                    onClick={handleSave}
                    disabled={isSaving}
                    className="text-xs bg-blue-600 hover:bg-blue-500 text-white"
                >
                    {isSaving ? 'Saving...' : saveStatus === 'success' ? 'Saved!' : 'Save Config'}
                    {!isSaving && saveStatus !== 'success' && <Save className="w-3 h-3 ml-2" />}
                </Button>
            </CardFooter>
        </Card>
    );
}
