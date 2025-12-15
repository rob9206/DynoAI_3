import { useState, useEffect, useRef, ImgHTMLAttributes } from 'react';
import { Skeleton } from './ui/skeleton';

interface OptimizedImageProps extends Omit<ImgHTMLAttributes<HTMLImageElement>, 'src'> {
  src: string;
  alt: string;
  /** Placeholder image to show while loading */
  placeholder?: string;
  /** Lazy load the image (default: true) */
  lazy?: boolean;
  /** Fade in animation duration in ms (default: 300) */
  fadeDuration?: number;
  /** Callback when image loads */
  onLoad?: () => void;
  /** Callback when image fails to load */
  onError?: () => void;
}

/**
 * Optimized image component with lazy loading and fade-in animation
 */
export function OptimizedImage({
  src,
  alt,
  placeholder,
  lazy = true,
  fadeDuration = 300,
  onLoad,
  onError,
  className = '',
  ...props
}: OptimizedImageProps) {
  const [isLoaded, setIsLoaded] = useState(false);
  const [isInView, setIsInView] = useState(!lazy);
  const [hasError, setHasError] = useState(false);
  const imgRef = useRef<HTMLImageElement>(null);

  // Intersection Observer for lazy loading
  useEffect(() => {
    if (!lazy || isInView) return;

    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            setIsInView(true);
            observer.disconnect();
          }
        });
      },
      {
        rootMargin: '50px', // Start loading 50px before entering viewport
      }
    );

    if (imgRef.current) {
      observer.observe(imgRef.current);
    }

    return () => {
      observer.disconnect();
    };
  }, [lazy, isInView]);

  const handleLoad = () => {
    setIsLoaded(true);
    onLoad?.();
  };

  const handleError = () => {
    setHasError(true);
    onError?.();
  };

  return (
    <div className={`relative overflow-hidden ${className}`}>
      {/* Skeleton loader */}
      {!isLoaded && !hasError && (
        <Skeleton className="absolute inset-0 w-full h-full" />
      )}

      {/* Actual image */}
      {isInView && !hasError && (
        <img
          ref={imgRef}
          src={src}
          alt={alt}
          onLoad={handleLoad}
          onError={handleError}
          className={`w-full h-full object-cover transition-opacity gpu-accelerated ${
            isLoaded ? 'opacity-100' : 'opacity-0'
          }`}
          style={{
            transitionDuration: `${fadeDuration}ms`,
          }}
          loading={lazy ? 'lazy' : 'eager'}
          decoding="async"
          {...props}
        />
      )}

      {/* Error state */}
      {hasError && (
        <div className="absolute inset-0 flex items-center justify-center bg-muted text-muted-foreground text-sm">
          Failed to load image
        </div>
      )}
    </div>
  );
}

/**
 * Hook for preloading images
 */
export function useImagePreload(urls: string[]) {
  const [loadedCount, setLoadedCount] = useState(0);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    if (urls.length === 0) {
      setIsLoading(false);
      return;
    }

    let loaded = 0;
    const images: HTMLImageElement[] = [];

    urls.forEach((url) => {
      const img = new Image();
      img.src = url;
      img.onload = () => {
        loaded++;
        setLoadedCount(loaded);
        if (loaded === urls.length) {
          setIsLoading(false);
        }
      };
      img.onerror = () => {
        loaded++;
        setLoadedCount(loaded);
        if (loaded === urls.length) {
          setIsLoading(false);
        }
      };
      images.push(img);
    });

    return () => {
      images.forEach((img) => {
        img.onload = null;
        img.onerror = null;
      });
    };
  }, [urls]);

  return {
    isLoading,
    loadedCount,
    progress: urls.length > 0 ? (loadedCount / urls.length) * 100 : 100,
  };
}

