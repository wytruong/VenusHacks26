import { Suspense, useEffect, useMemo, useRef, useState } from 'react'
import {
  AdditiveBlending,
  BackSide,
  BoxGeometry,
  Group,
  Mesh,
  MeshBasicMaterial,
  Vector3,
} from 'three'
import { Canvas, useFrame, useThree } from '@react-three/fiber'
import { AdaptiveDpr, Center, Html, Line, OrbitControls, useCursor, useGLTF } from '@react-three/drei'

const MODEL_URL = '/heart-model/scene.quality.glb'

export type MeshSelectPayload = {
  label: string
  description: string
  doctorQuestions: readonly [string, string]
}

/** Shared prompts for the info panel (not part of the anatomy mapping table). */
const DEFAULT_DOCTOR_QUESTIONS: readonly [string, string] = [
  'How does this area relate to my symptoms or risk factors?',
  'What follow-up would you recommend based on today\'s discussion?',
]

const HEART_MUSCLE_PAYLOAD: MeshSelectPayload = {
  label: 'Heart Muscle',
  description:
    'The main muscular wall of your heart that pumps blood through your body.',
  doctorQuestions: DEFAULT_DOCTOR_QUESTIONS,
}

const CORONARY_ARTERY_PAYLOAD: MeshSelectPayload = {
  label: 'Coronary Artery',
  description:
    'These vessels deliver fresh oxygenated blood directly to your heart muscle.',
  doctorQuestions: DEFAULT_DOCTOR_QUESTIONS,
}

const CARDIAC_VEIN_PAYLOAD: MeshSelectPayload = {
  label: 'Cardiac Vein',
  description:
    'These vessels carry used blood away from your heart muscle.',
  doctorQuestions: DEFAULT_DOCTOR_QUESTIONS,
}

const AORTA_PAYLOAD: MeshSelectPayload = {
  label: 'Aorta',
  description:
    'The main artery that carries oxygen-rich blood from your heart to the rest of your body.',
  doctorQuestions: DEFAULT_DOCTOR_QUESTIONS,
}

const PULMONARY_ARTERY_PAYLOAD: MeshSelectPayload = {
  label: 'Pulmonary Artery',
  description:
    'This vessel carries blood from your heart to your lungs to pick up oxygen.',
  doctorQuestions: DEFAULT_DOCTOR_QUESTIONS,
}

const HEART_REGION_PAYLOAD: MeshSelectPayload = {
  label: 'Heart Region',
  description:
    "This mesh isn't covered by the numbered Object map—your clinician can tie it to imaging.",
  doctorQuestions: DEFAULT_DOCTOR_QUESTIONS,
}

type HeartCalloutDef = {
  key: string
  label: string
  meshName: string
  offset: [number, number, number]
}

type HeartCalloutAnchor = {
  key: string
  label: string
  position: Vector3
  labelPosition: Vector3
}

const HEART_CALLOUT_DEFS: HeartCalloutDef[] = [
  {
    key: 'heart-muscle',
    label: 'Heart Muscle',
    meshName: 'Object_7',
    offset: [-0.34, 0.16, 0.06],
  },
  {
    key: 'coronary-artery',
    label: 'Coronary Artery',
    meshName: 'Object_18',
    offset: [0.32, 0.14, 0.08],
  },
  {
    key: 'cardiac-vein',
    label: 'Cardiac Vein',
    meshName: 'Object_29',
    offset: [-0.32, -0.1, 0.08],
  },
  {
    key: 'aorta',
    label: 'Aorta',
    meshName: 'Object_35',
    offset: [0.28, 0.26, 0.06],
  },
  {
    key: 'pulmonary-artery',
    label: 'Pulmonary Artery',
    meshName: 'Object_39',
    offset: [-0.28, 0.32, 0.06],
  },
]

function meshSelectPayloadFromName(meshName: string): MeshSelectPayload {
  const match = /^Object_(\d+)$/i.exec(meshName.trim())
  if (!match) return HEART_REGION_PAYLOAD
  const id = Number.parseInt(match[1], 10)
  if (Number.isNaN(id)) return HEART_REGION_PAYLOAD
  if (id >= 2 && id <= 15) return HEART_MUSCLE_PAYLOAD
  if (id >= 16 && id <= 25) return CORONARY_ARTERY_PAYLOAD
  if (id >= 26 && id <= 32) return CARDIAC_VEIN_PAYLOAD
  if (id >= 33 && id <= 37) return AORTA_PAYLOAD
  if (id >= 38 && id <= 42) return PULMONARY_ARTERY_PAYLOAD
  return HEART_REGION_PAYLOAD
}

function buildCalloutAnchors(scene: Group): HeartCalloutAnchor[] {
  const visualMeshes = new Map<string, Mesh>()
  scene.updateWorldMatrix(true, true)
  scene.traverse((obj) => {
    if ((obj as Mesh).isMesh && !obj.userData.heartPickProxy) {
      visualMeshes.set(obj.name, obj as Mesh)
    }
  })

  return HEART_CALLOUT_DEFS.flatMap((def) => {
    const mesh = visualMeshes.get(def.meshName)
    if (!mesh) return []

    mesh.geometry.computeBoundingBox()
    const box = mesh.geometry.boundingBox
    if (!box || box.isEmpty()) return []

    const position = new Vector3()
    box.getCenter(position)
    mesh.localToWorld(position)
    scene.worldToLocal(position)

    return [
      {
        key: def.key,
        label: def.label,
        position,
        labelPosition: position.clone().add(new Vector3(...def.offset)),
      },
    ]
  })
}

function HeartCallouts({
  anchors,
}: {
  anchors: HeartCalloutAnchor[]
}) {
  return anchors.map((anchor) => (
    <group key={anchor.key}>
      <Line
        points={[anchor.position, anchor.labelPosition]}
        color="#ffb3c1"
        lineWidth={1.35}
        transparent
        opacity={0.78}
      />
      <mesh position={anchor.position}>
        <sphereGeometry args={[0.012, 12, 12]} />
        <meshBasicMaterial color="#ffd1d8" transparent opacity={0.92} />
      </mesh>
      <Html
        center
        position={anchor.labelPosition}
        style={{ pointerEvents: 'none', userSelect: 'none' }}
      >
        <div className="rounded-full border border-white/25 bg-[#2a0d12]/75 px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.22em] text-rose-50 shadow-[0_0_20px_rgba(255,112,145,0.35)] backdrop-blur-md whitespace-nowrap">
          {anchor.label}
        </div>
      </Html>
    </group>
  ))
}

function SelectedMeshGlow({
  mesh,
}: {
  mesh: Mesh | null
}) {
  useEffect(() => {
    if (!mesh) return

    const material = new MeshBasicMaterial({
      blending: AdditiveBlending,
      color: '#ff4f75',
      depthWrite: false,
      opacity: 0.42,
      side: BackSide,
      transparent: true,
    })
    const glow = new Mesh(mesh.geometry, material)
    glow.name = `${mesh.name}_selected_glow`
    glow.userData.heartSelectedGlow = true
    glow.renderOrder = 2
    glow.scale.setScalar(1.022)
    glow.raycast = () => null
    mesh.add(glow)

    return () => {
      glow.parent?.remove(glow)
      material.dispose()
    }
  }, [mesh])

  return null
}

type HeartMeshProps = {
  onSelect: (payload: MeshSelectPayload | null) => void
  selectedMesh: Mesh | null
  onSelectMesh: (mesh: Mesh) => void
}

function HeartMesh({
  onSelect,
  selectedMesh,
  onSelectMesh,
}: HeartMeshProps) {
  const gltf = useGLTF(MODEL_URL)
  const regressPerformance = useThree((state) => state.performance.regress)
  const spinRef = useRef<Group>(null)
  const proxyToMeshRef = useRef(new WeakMap<Mesh, Mesh>())
  const hoverRef = useRef<Mesh | null>(null)
  const [cursorHover, setCursorHover] = useState(false)
  const calloutAnchors = useMemo(
    () => buildCalloutAnchors(gltf.scene),
    [gltf.scene],
  )
  useCursor(cursorHover)

  useEffect(() => {
    const scene = gltf.scene
    const proxyToMesh = proxyToMeshRef.current
    const proxyMaterial = new MeshBasicMaterial({
      colorWrite: false,
      depthWrite: false,
      opacity: 0,
      transparent: true,
    })
    const originalRaycasts = new Map<Mesh, Mesh['raycast']>()
    const proxyMeshes: Mesh[] = []
    const size = new Vector3()
    const center = new Vector3()

    const visualMeshes: Mesh[] = []
    scene.traverse((obj) => {
      if ((obj as Mesh).isMesh && !obj.userData.heartPickProxy) {
        visualMeshes.push(obj as Mesh)
      }
    })

    visualMeshes.forEach((mesh) => {
      const geometry = mesh.geometry
      geometry.computeBoundingBox()
      const box = geometry.boundingBox
      if (!box || box.isEmpty()) return

      box.getSize(size)
      box.getCenter(center)
      const proxyGeometry = new BoxGeometry(size.x, size.y, size.z)
      proxyGeometry.translate(center.x, center.y, center.z)
      const proxy = new Mesh(proxyGeometry, proxyMaterial)
      proxy.name = `${mesh.name}_pick_proxy`
      proxy.userData.heartPickProxy = true
      proxy.renderOrder = -1
      proxyToMesh.set(proxy, mesh)
      proxyMeshes.push(proxy)
      originalRaycasts.set(mesh, mesh.raycast)
      mesh.raycast = () => null
      mesh.add(proxy)
    })

    return () => {
      proxyMeshes.forEach((proxy) => {
        proxy.parent?.remove(proxy)
        proxy.geometry.dispose()
      })
      proxyMaterial.dispose()
      originalRaycasts.forEach((raycast, mesh) => {
        mesh.raycast = raycast
      })
      hoverRef.current = null
    }
  }, [gltf.scene])

  useFrame((state, delta) => {
    const spin = spinRef.current
    if (!spin) return
    const elapsed = state.clock.elapsedTime
    spin.rotation.y += delta * (0.2 + Math.sin(elapsed * 0.5) * 0.08)
    spin.position.y = Math.sin(elapsed * 0.8) * 0.05
  })

  return (
    <Center>
      <group
        onPointerMove={(e) => {
          regressPerformance()
          const mesh =
            e.object instanceof Mesh
              ? proxyToMeshRef.current.get(e.object) ?? null
              : null
          if (mesh === hoverRef.current) return
          hoverRef.current = mesh
          setCursorHover(mesh !== null)
        }}
        onPointerLeave={() => {
          hoverRef.current = null
          setCursorHover(false)
        }}
        onClick={(e) => {
          const mesh =
            e.object instanceof Mesh
              ? proxyToMeshRef.current.get(e.object) ?? null
              : null
          if (!mesh) return
          onSelectMesh(mesh)
          onSelect(meshSelectPayloadFromName(mesh.name))
          e.stopPropagation()
        }}
      >
        <group ref={spinRef}>
          <primitive object={gltf.scene} />
          <HeartCallouts anchors={calloutAnchors} />
        </group>
        <SelectedMeshGlow mesh={selectedMesh} />
      </group>
    </Center>
  )
}

useGLTF.preload(MODEL_URL)

type HeartModelProps = {
  onSelect: (payload: MeshSelectPayload | null) => void
}

export default function HeartModel({
  onSelect,
}: HeartModelProps) {
  const [selectedMesh, setSelectedMesh] = useState<Mesh | null>(null)

  const handlePointerMissed = () => {
    setSelectedMesh(null)
    onSelect(null)
  }

  return (
    <div className="fixed inset-0 h-screen w-screen bg-[#1a0a0a]">
      <Canvas
        className="h-full w-full touch-none"
        camera={{ position: [0, 0.08, 1.35], fov: 42 }}
        dpr={[0.75, 1.25]}
        gl={{ antialias: true, powerPreference: 'high-performance' }}
        onPointerMissed={handlePointerMissed}
      >
        <color attach="background" args={['#1a0a0a']} />
        <ambientLight intensity={1.65} />
        <pointLight
          color="#FFB3B3"
          position={[1.25, 1.6, 2.2]}
          intensity={1.4}
          distance={14}
          decay={2}
        />
        <directionalLight
          color="#ffffff"
          intensity={1.75}
          position={[0, 5, 10]}
        />
        <Suspense fallback={null}>
          <HeartMesh
            onSelect={onSelect}
            selectedMesh={selectedMesh}
            onSelectMesh={setSelectedMesh}
          />
        </Suspense>
        <AdaptiveDpr />
        <OrbitControls makeDefault />
      </Canvas>
    </div>
  )
}
