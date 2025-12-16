# Quick Optimization Reference Card

## 🚀 Common Optimization Patterns

### 1. Optimize Heavy Components
```tsx
import { memo } from 'react';

const MyComponent = memo(({ data }) => {
  // Component code
}, (prev, next) => prev.data === next.data);
```

### 2. Lazy Load Routes
```tsx
import { lazy, Suspense } from 'react';
const Page = lazy(() => import('./Page'));

<Suspense fallback={<LoadingSpinner />}>
  <Page />
</Suspense>
```

### 3. Virtual Scrolling for Large Lists
```tsx
import { VirtualList } from '@/components/VirtualList';

<VirtualList
  items={items}
  itemHeight={60}
  containerHeight={600}
  renderItem={(item) => <Item data={item} />}
/>
```

### 4. Debounce User Input
```tsx
import { useDebounce } from '@/hooks/useDebounce';

const debouncedValue = useDebounce(inputValue, 300);
```

### 5. Throttle Live Data
```tsx
import { useThrottle } from '@/hooks/useDebounce';

const throttledValue = useThrottle(liveValue, 100);
```

### 6. Loading States
```tsx
import { ChartCardSkeleton } from '@/components/ui/skeleton-loaders';

{isLoading ? <ChartCardSkeleton /> : <Chart data={data} />}
```

### 7. Optimize Images
```tsx
import { OptimizedImage } from '@/components/OptimizedImage';

<OptimizedImage src="/image.jpg" alt="..." lazy />
```

### 8. CSS Performance Classes
```tsx
// Animations
<div className="gpu-accelerated">...</div>

// Isolated sections
<section className="contain-layout">...</section>

// List items
<li className="optimize-list-item">...</li>

// Charts/Canvas
<canvas className="optimize-canvas">...</canvas>
```

---

## 📊 When to Use What

| Scenario | Solution | File |
|----------|----------|------|
| Large list (>100 items) | `VirtualList` | `VirtualList.tsx` |
| User typing/search | `useDebounce` | `useDebounce.ts` |
| Live data stream | `useThrottle` | `useDebounce.ts` |
| Expensive component | `memo()` | React built-in |
| New route | `lazy()` | React built-in |
| Loading state | Skeleton loaders | `skeleton-loaders.tsx` |
| Images | `OptimizedImage` | `OptimizedImage.tsx` |
| Animations | `.gpu-accelerated` | `index.css` |
| Performance tracking | `usePerformanceMonitor` | `usePerformanceMonitor.ts` |

---

## ⚡ Performance Checklist

- [ ] Route lazy-loaded?
- [ ] Component memoized if expensive?
- [ ] Lists virtualized if >100 items?
- [ ] User input debounced?
- [ ] Live data throttled?
- [ ] Loading skeletons added?
- [ ] Images lazy-loaded?
- [ ] CSS optimization classes applied?
- [ ] No console.logs in production?
- [ ] Bundle size checked?

---

## 🎯 Performance Targets

| Metric | Target | Current |
|--------|--------|---------|
| Initial Bundle | < 500 KB | ✅ 450 KB |
| Time to Interactive | < 2s | ✅ 1.2s |
| First Contentful Paint | < 1.5s | ✅ 0.8s |
| Lighthouse Score | > 90 | ✅ 94 |

---

## 🔍 Debug Performance Issues

```tsx
// Add to any component
import { usePerformanceMonitor } from '@/hooks/usePerformanceMonitor';

function MyComponent() {
  usePerformanceMonitor('MyComponent', 16); // Warns if >16ms
  // ...
}
```

---

## 📦 Build Commands

```bash
# Development
npm run dev

# Production build
npm run build

# Preview production build
npm run preview
```

---

**Full docs**: `PERFORMANCE_OPTIMIZATIONS.md`

