import { useEffect, useRef } from 'react';
import * as THREE from 'three';
import type { VEData } from '@/lib/types';

interface VESurfaceProps {
  data: VEData;
  type: 'before' | 'after';
}

export function VESurface({ data, type }: VESurfaceProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const sceneRef = useRef<THREE.Scene | null>(null);
  const rendererRef = useRef<THREE.WebGLRenderer | null>(null);
  const cameraRef = useRef<THREE.PerspectiveCamera | null>(null);
  const meshRef = useRef<THREE.Mesh | null>(null);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const width = container.clientWidth || 600;
    const height = container.clientHeight || 500;

    const scene = new THREE.Scene();
    // Use a color that matches the semantic bg-muted/10 or similar, but in hex.
    // Since we can't easily read CSS vars here without a helper, let's use a neutral dark background
    // that works with the 3D lighting. Or stick to a transparent background so CSS handles it.
    // Let's make it transparent to respect the parent container's background.
    // But Fog needs a color. Let's stick to the dark gray we had, or use the computed style if possible.
    
    // For now, let's use a dark slate to match the PRD dark theme or a very light gray for light theme.
    // A safer bet is a dark background for the 3D view as it makes the colored mesh pop.
    // Let's keep the dark background but ensure it matches the 'muted' color more closely if we were in dark mode.
    // Actually, let's use a transparent background for the renderer and scene, so the gradient CSS on the container shows through.
    // scene.background = null; // Transparent
    
    // However, Fog needs a solid color. 
    const bgColor = 0x111827; // gray-900 equivalent
    scene.background = new THREE.Color(bgColor); 
    scene.fog = new THREE.Fog(bgColor, 40, 100);
    
    sceneRef.current = scene;

    const camera = new THREE.PerspectiveCamera(50, width / height, 0.1, 1000);
    camera.position.set(35, 35, 35);
    camera.lookAt(0, 0, 0);
    cameraRef.current = camera;

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setSize(width, height);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    
    // Clear any existing canvas
    while (container.firstChild) {
      container.removeChild(container.firstChild);
    }
    
    container.appendChild(renderer.domElement);
    rendererRef.current = renderer;

    const ambientLight = new THREE.AmbientLight(0xffffff, 0.6);
    scene.add(ambientLight);

    const directionalLight1 = new THREE.DirectionalLight(0xffffff, 1.0);
    directionalLight1.position.set(15, 25, 15);
    directionalLight1.castShadow = true;
    scene.add(directionalLight1);

    const directionalLight2 = new THREE.DirectionalLight(0xffffff, 0.4);
    directionalLight2.position.set(-15, 15, -15);
    scene.add(directionalLight2);

    const rimLight = new THREE.DirectionalLight(0xffffff, 0.3);
    rimLight.position.set(0, 10, -20);
    scene.add(rimLight);

    const veData = type === 'before' ? data.before : data.after;
    const { geometry } = createSurfaceGeometry(data.rpm, data.load, veData, type);

    const material = new THREE.MeshStandardMaterial({
      vertexColors: true,
      metalness: 0.4,
      roughness: 0.3,
      side: THREE.DoubleSide,
      emissive: 0x000000,
      emissiveIntensity: 0.1
    });

    const mesh = new THREE.Mesh(geometry, material);
    mesh.castShadow = true;
    mesh.receiveShadow = true;
    scene.add(mesh);
    meshRef.current = mesh;

    createGradientGrid(scene, type);

    const axes = createAxes();
    scene.add(axes);

    let animationId: number;
    let isDragging = false;
    let previousMouseX = 0;
    let previousMouseY = 0;
    let rotationY = 0;
    let rotationX = -0.3;

    const onMouseDown = (event: MouseEvent) => {
      isDragging = true;
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
    };

    const onMouseLeave = () => {
      isDragging = false;
      container.style.cursor = 'grab';
    };

    container.style.cursor = 'grab';
    container.addEventListener('mousedown', onMouseDown);
    container.addEventListener('mousemove', onMouseMove);
    container.addEventListener('mouseup', onMouseUp);
    container.addEventListener('mouseleave', onMouseLeave);

    const animate = () => {
      animationId = requestAnimationFrame(animate);

      if (meshRef.current) {
        meshRef.current.rotation.y = rotationY;
        meshRef.current.rotation.x = rotationX;
      }

      renderer.render(scene, camera);
    };

    animate();

    const handleResize = () => {
      const newWidth = container.clientWidth;
      const newHeight = container.clientHeight;

      camera.aspect = newWidth / newHeight;
      camera.updateProjectionMatrix();
      renderer.setSize(newWidth, newHeight);
    };

    window.addEventListener('resize', handleResize);

    // Trigger resize after a short delay to ensure container is sized correctly
    setTimeout(handleResize, 100);

    return () => {
      cancelAnimationFrame(animationId);
      window.removeEventListener('resize', handleResize);
      container.removeEventListener('mousedown', onMouseDown);
      container.removeEventListener('mousemove', onMouseMove);
      container.removeEventListener('mouseup', onMouseUp);
      container.removeEventListener('mouseleave', onMouseLeave);
      renderer.dispose();
      geometry.dispose();
      material.dispose();
      // Check if child still exists before removing
      if (container.contains(renderer.domElement)) {
        container.removeChild(renderer.domElement);
      }
    };
  }, [data, type]);

  return (
    <div ref={containerRef} className="w-full h-full min-h-[500px] rounded-lg overflow-hidden bg-muted/20" />
  );
}

function createSurfaceGeometry(
  rpm: number[],
  load: number[],
  veValues: number[][],
  type: 'before' | 'after'
): { geometry: THREE.BufferGeometry; colors: number[] } {
  const geometry = new THREE.BufferGeometry();
  const vertices: number[] = [];
  const indices: number[] = [];
  const colors: number[] = [];

  const scaleX = 5;
  const scaleZ = 5;
  const scaleY = 0.25;

  let minVE = Infinity;
  let maxVE = -Infinity;

  for (let i = 0; i < rpm.length; i++) {
    for (let j = 0; j < load.length; j++) {
      const val = veValues[i][j];
      if (val !== null && !isNaN(val)) {
        minVE = Math.min(minVE, val);
        maxVE = Math.max(maxVE, val);
      }
    }
  }
  
  // Fallback if data is empty
  if (minVE === Infinity) {
      minVE = 0;
      maxVE = 100;
  }
  if (minVE === maxVE) {
      maxVE = minVE + 1;
  }

  for (let i = 0; i < rpm.length; i++) {
    for (let j = 0; j < load.length; j++) {
      const x = (i - rpm.length / 2) * scaleX;
      const z = (j - load.length / 2) * scaleZ;
      const val = veValues[i][j] !== null ? veValues[i][j] : 0;
      const y = val * scaleY;

      vertices.push(x, y, z);

      const normalized = (val - minVE) / (maxVE - minVE);
      const color = getGradientColor(normalized, type);
      colors.push(color.r, color.g, color.b);
    }
  }

  for (let i = 0; i < rpm.length - 1; i++) {
    for (let j = 0; j < load.length - 1; j++) {
      const a = i * load.length + j;
      const b = i * load.length + (j + 1);
      const c = (i + 1) * load.length + (j + 1);
      const d = (i + 1) * load.length + j;

      indices.push(a, b, d);
      indices.push(b, c, d);
    }
  }

  geometry.setAttribute('position', new THREE.Float32BufferAttribute(vertices, 3));
  geometry.setAttribute('color', new THREE.Float32BufferAttribute(colors, 3));
  geometry.setIndex(indices);
  geometry.computeVertexNormals();

  return { geometry, colors };
}

function getGradientColor(value: number, _type: 'before' | 'after'): { r: number; g: number; b: number } {
  if (value < 0.2) {
    const t = value / 0.2;
    return {
      r: 0.5 + t * 0.3,
      g: 0.0 + t * 0.0,
      b: 0.8 + t * 0.2
    };
  } else if (value < 0.4) {
    const t = (value - 0.2) / 0.2;
    return {
      r: 0.8 - t * 0.8,
      g: 0.0 + t * 0.0,
      b: 1.0 - t * 0.2
    };
  } else if (value < 0.6) {
    const t = (value - 0.4) / 0.2;
    return {
      r: 0.0 + t * 0.0,
      g: 0.0 + t * 0.8,
      b: 0.8 - t * 0.2
    };
  } else if (value < 0.8) {
    const t = (value - 0.6) / 0.2;
    return {
      r: 0.0 + t * 1.0,
      g: 0.8 + t * 0.2,
      b: 0.6 - t * 0.6
    };
  } else {
    const t = (value - 0.8) / 0.2;
    return {
      r: 1.0,
      g: 1.0 - t * 0.2,
      b: 0.0
    };
  }
}

function createGradientGrid(scene: THREE.Scene, _type: 'before' | 'after'): void {
  const gridSize = 50;
  const divisions = 25;
  const step = gridSize / divisions;

  const gridGroup = new THREE.Group();

  for (let i = 0; i <= divisions; i++) {
    const position = -gridSize / 2 + i * step;
    const alpha = i / divisions;

    const hue1 = (alpha * 0.8);
    const hue2 = (alpha * 0.8 + 0.1) % 1.0;

    const color1 = new THREE.Color().setHSL(hue1, 0.7, 0.5);
    const color2 = new THREE.Color().setHSL(hue2, 0.7, 0.5);

    const lineMaterialX = new THREE.LineBasicMaterial({
      color: color1,
      transparent: true,
      opacity: 0.2 + alpha * 0.2
    });

    const lineGeometryX = new THREE.BufferGeometry().setFromPoints([
      new THREE.Vector3(position, 0, -gridSize / 2),
      new THREE.Vector3(position, 0, gridSize / 2)
    ]);

    const lineX = new THREE.Line(lineGeometryX, lineMaterialX);
    gridGroup.add(lineX);

    const lineMaterialZ = new THREE.LineBasicMaterial({
      color: color2,
      transparent: true,
      opacity: 0.2 + alpha * 0.2
    });

    const lineGeometryZ = new THREE.BufferGeometry().setFromPoints([
      new THREE.Vector3(-gridSize / 2, 0, position),
      new THREE.Vector3(gridSize / 2, 0, position)
    ]);

    const lineZ = new THREE.Line(lineGeometryZ, lineMaterialZ);
    gridGroup.add(lineZ);
  }

  gridGroup.position.y = 0;
  scene.add(gridGroup);
}

function createAxes(): THREE.Group {
  const axesGroup = new THREE.Group();

  const axisLength = 20;

  const xMaterial = new THREE.LineBasicMaterial({ color: 0xff4444, linewidth: 2 });
  const xGeometry = new THREE.BufferGeometry().setFromPoints([
    new THREE.Vector3(0, 0, 0),
    new THREE.Vector3(axisLength, 0, 0)
  ]);
  const xAxis = new THREE.Line(xGeometry, xMaterial);
  axesGroup.add(xAxis);

  const yMaterial = new THREE.LineBasicMaterial({ color: 0x44ff44, linewidth: 2 });
  const yGeometry = new THREE.BufferGeometry().setFromPoints([
    new THREE.Vector3(0, 0, 0),
    new THREE.Vector3(0, axisLength, 0)
  ]);
  const yAxis = new THREE.Line(yGeometry, yMaterial);
  axesGroup.add(yAxis);

  const zMaterial = new THREE.LineBasicMaterial({ color: 0x4444ff, linewidth: 2 });
  const zGeometry = new THREE.BufferGeometry().setFromPoints([
    new THREE.Vector3(0, 0, 0),
    new THREE.Vector3(0, 0, axisLength)
  ]);
  const zAxis = new THREE.Line(zGeometry, zMaterial);
  axesGroup.add(zAxis);

  return axesGroup;
}
