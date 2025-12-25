import { toast as sonnerToast } from "sonner";
import { playUiSound } from "@/lib/ui-sounds";

type SonnerToast = typeof sonnerToast;

const wrap =
  <TArgs extends unknown[], TRet>(kind: Parameters<typeof playUiSound>[0], fn: (...args: TArgs) => TRet) =>
  (...args: TArgs) => {
    playUiSound(kind);
    return fn(...args);
  };

// Sonner's `toast` is both callable and has methods (success/error/info/...).
// We preserve the full API surface but add sound side-effects for common variants.
export const toast: SonnerToast = Object.assign(
  ((...args: Parameters<SonnerToast>) => sonnerToast(...args)) as SonnerToast,
  sonnerToast,
  {
    success: wrap("success", sonnerToast.success.bind(sonnerToast)),
    error: wrap("error", sonnerToast.error.bind(sonnerToast)),
    warning: wrap("warning", sonnerToast.warning.bind(sonnerToast)),
    info: wrap("info", sonnerToast.info.bind(sonnerToast)),
  } satisfies Partial<SonnerToast>
);


