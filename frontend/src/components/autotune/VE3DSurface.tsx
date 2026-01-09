import { useEffect, useRef, useMemo } from 'react';
import * as THREE from 'three';

interface VE3DSurfaceProps {
  grid: number[][];
  stage: number;
  highlightChanges?: boolean;
  originalGrid?: number[][];
  autoRotate?: boolean;
  className?: string;
}

// Color mapping for VE tables - matches HP Tuners/EFI Live style
// Green (low VE) -> Yellow -> Orange -> Red (high VE)
function getValueColor(value: number, min: number, max: number): THREE.Color {
  // Normalize to 0-1 range based on data extent
  const range = max - min || 1;
  const t = Math.max(0, Math.min(1, (value - min) / range));
  
  // Classic VE table gradient: green -> yellow -> orange -> red
  if (t < 0.25) {
    // Green to yellow-green
    const s = t / 0.25;
    return new THREE.Color().setHSL(0.33 - s * 0.08, 0.85, 0.4 + s * 0.1);
  } else if (t < 0.5) {
    // Yellow-green to yellow
    const s = (t - 0.25) / 0.25;
    return new THREE.Color().setHSL(0.25 - s * 0.1, 0.9, 0.5 + s * 0.05);
  } else if (t < 0.75) {
    // Yellow to orange
    const s = (t - 0.5) / 0.25;
    return new THREE.Color().setHSL(0.15 - s * 0.07, 0.95, 0.55 - s * 0.05);
  } else {
    // Orange to red
    const s = (t - 0.75) / 0.25;
    return new THREE.Color().setHSL(0.08 - s * 0.06, 0.95, 0.5 + s * 0.05);
  }
}

// Get change intensity color (for showing differences between stages)
function getChangeColor(original: number, current: number): THREE.Color {
  const diff = current - original; // Signed diff: positive = increased, negative = decreased
  const absDiff = Math.abs(diff);
  
  if (absDiff < 0.1) {
    // No significant change - dim gray
    return new THREE.Color(0.25, 0.25, 0.28);
  } else if (diff > 0) {
    // Value increased (smoothing added fuel) - green tones
    const intensity = Math.min(absDiff / 3, 1);
    return new THREE.Color().setHSL(0.38, 0.8, 0.35 + intensity * 0.35);
  } else {
    // Value decreased (smoothing removed fuel) - purple/magenta tones
    const intensity = Math.min(absDiff / 3, 1);
    return new THREE.Color().setHSL(0.82, 0.75, 0.35 + intensity * 0.35);
  }
}

export function VE3DSurface({
  grid,
  stage,
  highlightChanges = false,
  originalGrid,
  autoRotate = true,
  className = '',
}: VE3DSurfaceProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const sceneRef = useRef<THREE.Scene | null>(null);
  const rendererRef = useRef<THREE.WebGLRenderer | null>(null);
  const cameraRef = useRef<THREE.PerspectiveCamera | null>(null);
  const meshRef = useRef<THREE.Mesh | null>(null);
  const frameRef = useRef<number>(0);

  // Flatten grid for easier processing
  const flattenedData = useMemo(() => {
    const rows = grid.length;
    const cols = grid[0]?.length || 0;
    const values: number[] = [];
    let min = Infinity;
    let max = -Infinity;

    for (let r = 0; r < rows; r++) {
      for (let c = 0; c < cols; c++) {
        const val = grid[r][c];
        values.push(val);
        min = Math.min(min, val);
        max = Math.max(max, val);
      }
    }

    return { values, rows, cols, min, max };
  }, [grid]);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const width = container.clientWidth || 400;
    const height = container.clientHeight || 300;

    // Scene setup with darker background for better contrast
    const scene = new THREE.Scene();
    const bgColor = 0x0d0d12;
    scene.background = new THREE.Color(bgColor);
    scene.fog = new THREE.Fog(bgColor, 40, 100);
    sceneRef.current = scene;

    // Camera - positioned for better view of the surface
    const camera = new THREE.PerspectiveCamera(40, width / height, 0.1, 1000);
    camera.position.set(22, 18, 22);
    camera.lookAt(0, 2, 0);
    cameraRef.current = camera;

    // Renderer with higher quality
    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setSize(width, height);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.2;

    // Clear existing content
    while (container.firstChild) {
      container.removeChild(container.firstChild);
    }
    container.appendChild(renderer.domElement);
    rendererRef.current = renderer;

    // Enhanced lighting for better surface definition
    const ambientLight = new THREE.AmbientLight(0xffffff, 0.6);
    scene.add(ambientLight);

    // Key light - warm, from above-front
    const mainLight = new THREE.DirectionalLight(0xfff4e6, 1.4);
    mainLight.position.set(12, 25, 15);
    mainLight.castShadow = true;
    mainLight.shadow.mapSize.width = 1024;
    mainLight.shadow.mapSize.height = 1024;
    scene.add(mainLight);

    // Fill light - cool, from opposite side
    const fillLight = new THREE.DirectionalLight(0x9090ff, 0.5);
    fillLight.position.set(-15, 8, -12);
    scene.add(fillLight);

    // Rim light - warm accent from behind
    const rimLight = new THREE.DirectionalLight(0xffaa44, 0.6);
    rimLight.position.set(-5, 3, -20);
    scene.add(rimLight);

    // Bottom fill to show undersides
    const bottomLight = new THREE.DirectionalLight(0x444466, 0.3);
    bottomLight.position.set(0, -10, 0);
    scene.add(bottomLight);

    // Create surface geometry with better scaling for visibility
    const { rows, cols, min, max } = flattenedData;
    const geometry = new THREE.BufferGeometry();
    const vertices: number[] = [];
    const colors: number[] = [];
    const indices: number[] = [];

    // Scale to fit nicely in view - larger surface for better visibility
    const scaleX = 16 / cols;
    const scaleZ = 16 / rows;
    // Height scale normalized to data range for consistent appearance
    const heightRange = max - min;
    const scaleY = heightRange > 0 ? 0.45 : 1; // Normalize height so peak is ~8 units tall

    for (let r = 0; r < rows; r++) {
      for (let c = 0; c < cols; c++) {
        const x = (c - cols / 2) * scaleX;
        const z = (r - rows / 2) * scaleZ;
        const value = grid[r][c];
        // Center the surface vertically around y=0
        const y = (value - (min + max) / 2) * scaleY;

        vertices.push(x, y, z);

        // Color based on mode
        let color: THREE.Color;
        if (highlightChanges && originalGrid) {
          color = getChangeColor(originalGrid[r][c], value);
        } else {
          color = getValueColor(value, min, max);
        }
        colors.push(color.r, color.g, color.b);
      }
    }

    // Create triangles
    for (let r = 0; r < rows - 1; r++) {
      for (let c = 0; c < cols - 1; c++) {
        const a = r * cols + c;
        const b = r * cols + (c + 1);
        const c1 = (r + 1) * cols + (c + 1);
        const d = (r + 1) * cols + c;

        indices.push(a, b, d);
        indices.push(b, c1, d);
      }
    }

    geometry.setAttribute('position', new THREE.Float32BufferAttribute(vertices, 3));
    geometry.setAttribute('color', new THREE.Float32BufferAttribute(colors, 3));
    geometry.setIndex(indices);
    geometry.computeVertexNormals();

    // Material - shinier for better visual definition
    const material = new THREE.MeshStandardMaterial({
      vertexColors: true,
      metalness: 0.25,
      roughness: 0.35,
      side: THREE.DoubleSide,
      flatShading: false,
    });

    const mesh = new THREE.Mesh(geometry, material);
    mesh.castShadow = true;
    mesh.receiveShadow = true;
    scene.add(mesh);
    meshRef.current = mesh;

    // Minimal floor plane instead of grid (less distracting)
    const floorGeo = new THREE.PlaneGeometry(20, 20);
    const floorMat = new THREE.MeshBasicMaterial({ 
      color: 0x111118, 
      transparent: true, 
      opacity: 0.3,
      side: THREE.DoubleSide 
    });
    const floor = new THREE.Mesh(floorGeo, floorMat);
    floor.rotation.x = -Math.PI / 2;
    floor.position.y = -6;
    scene.add(floor);

    // Add axis labels as small glowing spheres
    const createAxisMarker = (pos: THREE.Vector3, color: number) => {
      const geo = new THREE.SphereGeometry(0.2);
      const mat = new THREE.MeshBasicMaterial({ color });
      const sphere = new THREE.Mesh(geo, mat);
      sphere.position.copy(pos);
      return sphere;
    };

    // Axis markers at edges
    scene.add(createAxisMarker(new THREE.Vector3(9, 0, 0), 0xff5555)); // MAP axis (red)
    scene.add(createAxisMarker(new THREE.Vector3(0, 6, 0), 0x55ff55)); // VE axis (green)
    scene.add(createAxisMarker(new THREE.Vector3(0, 0, 9), 0x5588ff)); // RPM axis (blue)

    // Mouse interaction
    let isDragging = false;
    let previousMouseX = 0;
    let previousMouseY = 0;
    let rotationY = 0;
    let rotationX = -0.35;
    // Much slower rotation - one full rotation takes ~60 seconds
    let autoRotateSpeed = autoRotate ? 0.0008 : 0;

    const onMouseDown = (event: MouseEvent) => {
      isDragging = true;
      autoRotateSpeed = 0;
      previousMouseX = event.clientX;
      previousMouseY = event.clientY;
      container.style.cursor = 'grabbing';
    };

    const onMouseMove = (event: MouseEvent) => {
      if (!isDragging) return;
      const deltaX = event.clientX - previousMouseX;
      const deltaY = event.clientY - previousMouseY;
      rotationY += deltaX * 0.01;
      rotationX += deltaY * 0.01;
      rotationX = Math.max(-Math.PI / 2, Math.min(Math.PI / 2, rotationX));
      previousMouseX = event.clientX;
      previousMouseY = event.clientY;
    };

    const onMouseUp = () => {
      isDragging = false;
      container.style.cursor = 'grab';
      if (autoRotate) {
        setTimeout(() => {
          if (!isDragging) autoRotateSpeed = 0.0008;
        }, 3000);
      }
    };

    container.style.cursor = 'grab';
    container.addEventListener('mousedown', onMouseDown);
    container.addEventListener('mousemove', onMouseMove);
    container.addEventListener('mouseup', onMouseUp);
    container.addEventListener('mouseleave', onMouseUp);

    // Animation loop
    const animate = () => {
      frameRef.current = requestAnimationFrame(animate);

      if (meshRef.current) {
        rotationY += autoRotateSpeed;
        meshRef.current.rotation.y = rotationY;
        meshRef.current.rotation.x = rotationX;
      }

      renderer.render(scene, camera);
    };

    animate();

    // Handle resize
    const handleResize = () => {
      const newWidth = container.clientWidth;
      const newHeight = container.clientHeight;
      camera.aspect = newWidth / newHeight;
      camera.updateProjectionMatrix();
      renderer.setSize(newWidth, newHeight);
    };

    window.addEventListener('resize', handleResize);
    setTimeout(handleResize, 100);

    return () => {
      cancelAnimationFrame(frameRef.current);
      window.removeEventListener('resize', handleResize);
      container.removeEventListener('mousedown', onMouseDown);
      container.removeEventListener('mousemove', onMouseMove);
      container.removeEventListener('mouseup', onMouseUp);
      container.removeEventListener('mouseleave', onMouseUp);
      renderer.dispose();
      geometry.dispose();
      material.dispose();
      if (container.contains(renderer.domElement)) {
        container.removeChild(renderer.domElement);
      }
    };
  }, [grid, stage, highlightChanges, originalGrid, autoRotate, flattenedData]);

  return (
    <div
      ref={containerRef}
      className={`w-full h-full min-h-[300px] rounded-xl overflow-hidden ${className}`}
    />
  );
}
