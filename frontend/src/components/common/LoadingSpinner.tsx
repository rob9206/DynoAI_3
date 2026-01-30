import { Gauge } from 'lucide-react';

export default function LoadingSpinner() {
  return (
    <div className="flex items-center justify-center min-h-[60vh]">
      <div className="flex flex-col items-center gap-4">
        <div className="relative">
          <div className="absolute inset-0 bg-gradient-to-r from-orange-500 to-red-600 rounded-full blur-xl opacity-50 animate-pulse" />
          <div className="relative p-4 bg-gradient-to-br from-orange-500 to-red-600 rounded-full animate-spin-slow">
            <Gauge className="h-8 w-8 text-white" />
          </div>
        </div>
        <p className="text-sm text-muted-foreground animate-pulse">Loading...</p>
      </div>
    </div>
  );
}

