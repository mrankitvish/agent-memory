import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { forceSimulation, forceLink, forceManyBody, forceCenter, forceCollide } from 'd3-force-3d';

export const colors = { semantic: '#087f71', episodic: '#4268ce', procedural: '#a37b15', profile: '#be466b', working: '#697c84' };

export function createGraph(container, onSelect) {
  const scene = new THREE.Scene();
  scene.background = new THREE.Color('#f5f8f6');
  const camera = new THREE.PerspectiveCamera(45, 1, 0.1, 5000);
  const renderer = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: true });
  renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
  renderer.domElement.setAttribute('aria-label', '3D graph of stored memories');
  container.append(renderer.domElement);
  const controls = new OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;
  controls.autoRotateSpeed = 0.4;
  controls.minDistance = 15;
  controls.maxDistance = 1800;
  controls.listenToKeyEvents(container);
  const group = new THREE.Group();
  scene.add(group);
  scene.add(new THREE.HemisphereLight(0xffffff, 0x63796c, 2.5));
  const light = new THREE.DirectionalLight(0xffffff, 2);
  light.position.set(20, 60, 40);
  scene.add(light);
  const grid = new THREE.GridHelper(1000, 50, '#d8e3dd', '#e5ede8');
  grid.position.y = -70;
  scene.add(grid);
  let meshes = [], labels = [], radius = 50, labelVisible = true, frame, active = true;
  const raycaster = new THREE.Raycaster();
  const pointer = new THREE.Vector2();
  let pointerStart = null;
  const tooltip = document.querySelector('#graph-tooltip');

  function fit() {
    controls.target.set(0, 0, 0);
    const narrowFov = Math.min(camera.fov * Math.PI / 180, 2 * Math.atan(Math.tan(camera.fov * Math.PI / 360) * camera.aspect));
    const distance = Math.max(100, (radius + 25) / Math.sin(narrowFov / 2));
    camera.position.set(distance * .25, distance * .3, distance);
    controls.update();
  }

  function resize() {
    if (!container.clientWidth || !container.clientHeight) return;
    camera.aspect = container.clientWidth / container.clientHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(container.clientWidth, container.clientHeight);
  }
  new ResizeObserver(resize).observe(container);

  function titleSprite(title) {
    const canvas = document.createElement('canvas');
    canvas.width = 512; canvas.height = 80;
    const context = canvas.getContext('2d');
    context.fillStyle = '#ffffffed';
    context.fillRect(0, 0, 512, 80);
    context.font = '600 26px "Manrope Variable", sans-serif';
    context.fillStyle = '#273d32';
    context.textAlign = 'center';
    context.textBaseline = 'middle';
    context.fillText(title.length > 29 ? title.slice(0, 27) + '...' : title, 256, 40, 490);
    const texture = new THREE.CanvasTexture(canvas);
    const sprite = new THREE.Sprite(new THREE.SpriteMaterial({ map: texture, depthTest: false }));
    sprite.scale.set(36, 5.6, 1);
    sprite.visible = labelVisible;
    return sprite;
  }

  function setData(data) {
    group.traverse(object => {
      object.geometry?.dispose();
      object.material?.map?.dispose();
      object.material?.dispose();
    });
    group.clear(); meshes = []; labels = [];
    const nodes = data.nodes.map(node => ({ ...node }));
    const links = data.links.map(link => ({ ...link }));
    const simulation = forceSimulation(nodes, 3)
      .force('link', forceLink(links).id(node => node.id).distance(45).strength(.25))
      .force('charge', forceManyBody().strength(-95))
      .force('center', forceCenter(0, 0, 0))
      .force('collision', forceCollide(13)).stop();
    simulation.tick(120);
    radius = 30;
    for (const node of nodes) {
      const mesh = new THREE.Mesh(new THREE.IcosahedronGeometry(3.3, 2), new THREE.MeshStandardMaterial({ color: colors[node.memory_type], roughness: .38, metalness: .1 }));
      mesh.position.set(node.x || 0, node.y || 0, node.z || 0);
      mesh.userData = node;
      group.add(mesh); meshes.push(mesh);
      radius = Math.max(radius, mesh.position.length());
      const label = titleSprite(node.title);
      label.position.copy(mesh.position).add(new THREE.Vector3(0, -7, 0));
      group.add(label); labels.push(label);
    }
    const points = [];
    for (const link of links) points.push(new THREE.Vector3(link.source.x, link.source.y, link.source.z), new THREE.Vector3(link.target.x, link.target.y, link.target.z));
    if (points.length) group.add(new THREE.LineSegments(new THREE.BufferGeometry().setFromPoints(points), new THREE.LineBasicMaterial({ color: '#83aaa0', transparent: true, opacity: .65 })));
    grid.position.y = -radius - 20;
    container.dataset.nodes = String(nodes.length);
    container.dataset.links = String(links.length);
    resize(); fit();
  }

  function hit(event) {
    const rect = renderer.domElement.getBoundingClientRect();
    pointer.set((event.clientX - rect.left) / rect.width * 2 - 1, -(event.clientY - rect.top) / rect.height * 2 + 1);
    raycaster.setFromCamera(pointer, camera);
    return raycaster.intersectObjects(meshes)[0]?.object;
  }
  renderer.domElement.addEventListener('pointerdown', event => { pointerStart = [event.clientX, event.clientY]; });
  renderer.domElement.addEventListener('pointerup', event => {
    if (pointerStart && Math.hypot(event.clientX - pointerStart[0], event.clientY - pointerStart[1]) < 6) {
      const object = hit(event);
      if (object) onSelect(object.userData.id);
    }
    pointerStart = null;
  });
  renderer.domElement.addEventListener('pointermove', event => {
    const object = hit(event);
    tooltip.hidden = !object;
    if (object) tooltip.textContent = `${object.userData.title} | ${object.userData.memory_type}`;
    renderer.domElement.style.cursor = object ? 'pointer' : 'grab';
  });
  renderer.domElement.addEventListener('pointerleave', () => { tooltip.hidden = true; });
  function animate() {
    frame = requestAnimationFrame(animate);
    if (!active || document.hidden) return;
    controls.update(); renderer.render(scene, camera);
  }
  resize(); fit(); animate();
  return {
    setData, fit,
    zoom(factor) { camera.position.sub(controls.target).multiplyScalar(factor).add(controls.target); controls.update(); },
    labels(value) { labelVisible = value; labels.forEach(label => { label.visible = value; }); },
    rotate(value) { controls.autoRotate = value; },
    active(value) { active = value; if (value) resize(); },
    dispose() { cancelAnimationFrame(frame); controls.dispose(); renderer.dispose(); },
  };
}