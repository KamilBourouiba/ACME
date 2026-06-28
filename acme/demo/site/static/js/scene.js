/**
 * Erebor Three.js scene — instanced globe, arc links, polished motion.
 * No generic gradient blobs — deliberate Palantir-adjacent aesthetic.
 */
import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";

const COLORS = {
  repo: new THREE.Color("#5b8def"),
  paper: new THREE.Color("#f0b429"),
  place: new THREE.Color("#3dd6c6"),
  org: new THREE.Color("#a78bfa"),
};

export class EreborScene {
  constructor(canvas) {
    this.canvas = canvas;
    this.nodes = [];
    this.autoRotate = true;
    this.showArcs = true;
    this.selectedId = null;
    this._onSelect = null;

    this.renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true });
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    this.renderer.setClearColor(0x030508, 1);

    this.scene = new THREE.Scene();
    this.camera = new THREE.PerspectiveCamera(48, 1, 0.1, 100);
    this.camera.position.set(0, 0.4, 3.2);

    this.controls = new OrbitControls(this.camera, canvas);
    this.controls.enableDamping = true;
    this.controls.dampingFactor = 0.06;
    this.controls.minDistance = 1.8;
    this.controls.maxDistance = 6;
    this.controls.autoRotate = true;
    this.controls.autoRotateSpeed = 0.35;

    const amb = new THREE.AmbientLight(0x404860, 0.6);
    const key = new THREE.DirectionalLight(0x3dd6c6, 0.9);
    key.position.set(2, 3, 4);
    this.scene.add(amb, key);

    this._globe = this._buildGlobe();
    this.scene.add(this._globe);

    this._nodeGroup = new THREE.Group();
    this._arcGroup = new THREE.Group();
    this.scene.add(this._nodeGroup, this._arcGroup);

    this._raycaster = new THREE.Raycaster();
    this._pointer = new THREE.Vector2();
    this._meshes = new Map();

    canvas.addEventListener("pointermove", (e) => this._onPointer(e));
    canvas.addEventListener("click", (e) => this._onClick(e));
    window.addEventListener("resize", () => this._resize());

    this._resize();
    this._animate();
  }

  onSelect(fn) {
    this._onSelect = fn;
  }

  setGraph(data) {
    this.nodes = data.nodes || [];
    const edges = data.edges || [];
    this._rebuildNodes();
    this._rebuildArcs(edges);
  }

  selectNode(id) {
    this.selectedId = id;
    for (const [nid, mesh] of this._meshes) {
      const sel = nid === id;
      mesh.scale.setScalar(sel ? 1.6 : 1);
      mesh.material.emissiveIntensity = sel ? 1.2 : 0.35;
    }
  }

  setAutoRotate(on) {
    this.autoRotate = on;
    this.controls.autoRotate = on;
  }

  setShowArcs(on) {
    this.showArcs = on;
    this._arcGroup.visible = on;
  }

  _buildGlobe() {
    const geo = new THREE.IcosahedronGeometry(1, 4);
    const mat = new THREE.MeshStandardMaterial({
      color: 0x0a1018,
      roughness: 0.85,
      metalness: 0.15,
      transparent: true,
      opacity: 0.92,
    });
    const mesh = new THREE.Mesh(geo, mat);
    const wire = new THREE.LineSegments(
      new THREE.WireframeGeometry(new THREE.IcosahedronGeometry(1.002, 3)),
      new THREE.LineBasicMaterial({ color: 0x1a2535, transparent: true, opacity: 0.35 })
    );
    mesh.add(wire);

    const pts = [];
    for (let i = 0; i < 1200; i++) {
      const v = new THREE.Vector3().randomDirection().multiplyScalar(1.01 + Math.random() * 0.02);
      pts.push(v.x, v.y, v.z);
    }
    const pGeo = new THREE.BufferGeometry();
    pGeo.setAttribute("position", new THREE.Float32BufferAttribute(pts, 3));
    const particles = new THREE.Points(
      pGeo,
      new THREE.PointsMaterial({ color: 0x3dd6c6, size: 0.008, transparent: true, opacity: 0.45 })
    );
    mesh.add(particles);
    return mesh;
  }

  _latLngToVec(lat, lng, r = 1.06) {
    const phi = (90 - lat) * (Math.PI / 180);
    const theta = (lng + 180) * (Math.PI / 180);
    return new THREE.Vector3(
      -r * Math.sin(phi) * Math.cos(theta),
      r * Math.cos(phi),
      r * Math.sin(phi) * Math.sin(theta)
    );
  }

  _rebuildNodes() {
    while (this._nodeGroup.children.length) {
      const c = this._nodeGroup.children.pop();
      c.geometry?.dispose();
      c.material?.dispose();
    }
    this._meshes.clear();

    for (const node of this.nodes) {
      const color = COLORS[node.kind] || COLORS.repo;
      const geo = new THREE.SphereGeometry(0.028, 16, 16);
      const mat = new THREE.MeshStandardMaterial({
        color,
        emissive: color,
        emissiveIntensity: 0.35,
        roughness: 0.3,
        metalness: 0.6,
      });
      const mesh = new THREE.Mesh(geo, mat);
      const lat = node.lat ?? (Math.random() - 0.5) * 120;
      const lng = node.lng ?? (Math.random() - 0.5) * 360;
      mesh.position.copy(this._latLngToVec(lat, lng));
      mesh.userData = { id: node.id, node };
      this._nodeGroup.add(mesh);
      this._meshes.set(node.id, mesh);
    }
  }

  _rebuildArcs(edges) {
    while (this._arcGroup.children.length) {
      const c = this._arcGroup.children.pop();
      c.geometry?.dispose();
      c.material?.dispose();
    }
    if (!this.showArcs) return;

    const pos = new Map(this.nodes.map((n) => [n.id, n]));
    for (const e of edges) {
      const a = pos.get(e.from);
      const b = pos.get(e.to);
      if (!a || !b) continue;
      const v0 = this._latLngToVec(a.lat ?? 0, a.lng ?? 0, 1.06);
      const v1 = this._latLngToVec(b.lat ?? 0, b.lng ?? 0, 1.06);
      const mid = v0.clone().add(v1).normalize().multiplyScalar(1.35);
      const curve = new THREE.QuadraticBezierCurve3(v0, mid, v1);
      const pts = curve.getPoints(48);
      const geo = new THREE.BufferGeometry().setFromPoints(pts);
      const line = new THREE.Line(
        geo,
        new THREE.LineBasicMaterial({ color: 0x3dd6c6, transparent: true, opacity: 0.22 })
      );
      this._arcGroup.add(line);
    }
  }

  _onPointer(ev) {
    const rect = this.canvas.getBoundingClientRect();
    this._pointer.x = ((ev.clientX - rect.left) / rect.width) * 2 - 1;
    this._pointer.y = -((ev.clientY - rect.top) / rect.height) * 2 + 1;
    this._raycaster.setFromCamera(this._pointer, this.camera);
    const hits = this._raycaster.intersectObjects(this._nodeGroup.children);
    this.canvas.style.cursor = hits.length ? "pointer" : "grab";
  }

  _onClick(ev) {
    const rect = this.canvas.getBoundingClientRect();
    this._pointer.x = ((ev.clientX - rect.left) / rect.width) * 2 - 1;
    this._pointer.y = -((ev.clientY - rect.top) / rect.height) * 2 + 1;
    this._raycaster.setFromCamera(this._pointer, this.camera);
    const hits = this._raycaster.intersectObjects(this._nodeGroup.children);
    if (hits.length && this._onSelect) {
      const { id, node } = hits[0].object.userData;
      this.selectNode(id);
      this._onSelect(node);
    }
  }

  _resize() {
    const w = this.canvas.clientWidth;
    const h = this.canvas.clientHeight;
    this.camera.aspect = w / h;
    this.camera.updateProjectionMatrix();
    this.renderer.setSize(w, h, false);
  }

  _animate() {
    requestAnimationFrame(() => this._animate());
    this._globe.rotation.y += 0.0004;
    this.controls.update();
    this.renderer.render(this.scene, this.camera);
  }
}

window.EreborScene = EreborScene;
