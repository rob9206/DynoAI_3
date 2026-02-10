/// <reference types="vite/client" />

interface ImportMetaEnv {
    readonly VITE_API_URL?: string;
    readonly VITE_API_KEY?: string;
    readonly VITE_V3_MATERIALIZE_FALLBACK?: string;
}

interface ImportMeta {
    readonly env: ImportMetaEnv;
}
