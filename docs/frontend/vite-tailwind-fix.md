# Vite Tailwind CSS Fix for animate-ping Error

## Problem
The Vite compiler is failing because of this line:
```tsx
<span className={`animate-ping absolute inline-flex h-full w-full rounded-full ${audioKnockDetected ? 'bg-orange-400' : 'bg-red-400'} opacity-75`}></span>
```

The issue is that Tailwind can't statically analyze classes inside template literals when they include dynamic class names. This prevents Tailwind from including the classes in the final bundle.

## Solution
Create separate class strings for conditional logic:

```tsx
// Option 1: Separate element for each condition
<span className="absolute -top-1 -right-1 flex h-3 w-3">
  {audioKnockDetected ? (
    <>
      <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-orange-400 opacity-75" />
      <span className="relative inline-flex rounded-full h-3 w-3 bg-orange-500" />
    </>
  ) : (
    <>
      <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-red-400 opacity-75" />
      <span className="relative inline-flex rounded-full h-3 w-3 bg-red-500" />
    </>
  )}
</span>

// Option 2: Use CSS custom properties or class selectors
<span className={`absolute -top-1 -right-1 flex h-3 w-3 ${audioKnockDetected ? 'knock-detected' : 'recording-active'}`}>
  <span className="animate-ping absolute inline-flex h-full w-full rounded-full opacity-75" />
  <span className="relative inline-flex rounded-full h-3 w-3" />
</span>

// CSS to add to global styles:
/*.knock-detected .animate-ping { background-color: rgb(251 146 60); }*/
/*.recording-active .animate-ping { background-color: rgb(248 113 113); }*/
/*.knock-detected span:last-child { background-color: rgb(249 115 22); }*/
/*.recording-active span:last-child { background-color: rgb(239 68 68); }*/

// Option 3: Create classes with both animation and color
<span className={`absolute -top-1 -right-1 flex h-3 w-3`}>
  <span className={`${audioKnockDetected ? 
    'animate-ping-knock absolute inline-flex h-full w-full rounded-full opacity-75' : 
    'animate-ping-recording absolute inline-flex h-full w-full rounded-full opacity-75'}`} />
  <span className={`${audioKnockDetected ? 
    'relative inline-flex rounded-full h-3 w-3 bg-orange-500' : 
    'relative inline-flex rounded-full h-3 w-3 bg-red-500'}`} />
</span>

// Add these classes to Tailwind config:
// .animate-ping-knock { animation: ping 2s cubic-bezier(0,0,0.2,1) infinite; background-color: rgb(251 146 60); }
// .animate-ping-recording { animation: ping 2s cubic-bezier(0,0,0.2,1) infinite; background-color: rgb(248 113 113); }
```

## Recommended Fix
Use Option 1 for immediate resolution. It separates the conditional logic cleanly and ensures all Tailwind classes are statically analyzable.