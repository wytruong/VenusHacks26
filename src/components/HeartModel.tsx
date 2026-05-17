import {
  Suspense,
  type Dispatch,
  type SetStateAction,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react'
import {
  BoxGeometry,
  Group,
  Mesh,
  MeshBasicMaterial,
  MeshStandardMaterial,
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

const HEART_MUSCLE_PAYLOAD: MeshSelectPayload = {
  label: 'Heart Muscle',
  description:
    'The myocardium is the muscular wall of your heart. During pregnancy your heart pumps 50% more blood than usual, putting extra demand on this muscle.',
  doctorQuestions: [
    'Is my heart muscle showing any signs of strain from my pregnancy?',
    'Should I have an echocardiogram to check my heart function?',
  ],
}

const CORONARY_ARTERY_PAYLOAD: MeshSelectPayload = {
  label: 'Coronary Artery',
  description:
    'These vessels deliver oxygenated blood directly to your heart muscle. Reduced flow here can cause chest pain or shortness of breath, symptoms sometimes mistaken for normal pregnancy discomfort.',
  doctorQuestions: [
    'Could my chest tightness be related to my coronary arteries?',
    'What symptoms should make me call you immediately?',
  ],
}

const CARDIAC_VEIN_PAYLOAD: MeshSelectPayload = {
  label: 'Cardiac Vein',
  description:
    'These vessels carry used blood away from your heart muscle. They work harder during pregnancy as your blood volume increases significantly.',
  doctorQuestions: [
    'Is my blood volume within a healthy range for my stage of pregnancy?',
    'Are there signs of fluid retention I should watch for?',
  ],
}

const AORTA_PAYLOAD: MeshSelectPayload = {
  label: 'Aorta',
  description:
    'The main artery carrying oxygen-rich blood from your heart to your body and your baby. Blood pressure directly affects how hard your heart works to pump through this vessel.',
  doctorQuestions: [
    'How does my blood pressure affect blood flow to my baby?',
    'What is a safe blood pressure range for my stage of pregnancy?',
  ],
}

const PULMONARY_ARTERY_PAYLOAD: MeshSelectPayload = {
  label: 'Pulmonary Artery',
  description:
    'This vessel carries blood from your heart to your lungs. Pregnant women have a higher risk of pulmonary complications including blood clots.',
  doctorQuestions: [
    'Am I at risk for a pulmonary embolism during my pregnancy?',
    'What symptoms of a blood clot should I watch for?',
  ],
}

const HEART_REGION_PAYLOAD: MeshSelectPayload = {
  label: 'Heart Region',
  description:
    'Every part of your heart works harder during pregnancy. Your cardiac output increases by up to 50% to support your growing baby.',
  doctorQuestions: [
    'Is my overall heart function being monitored during my pregnancy?',
    'What cardiac symptoms should prompt an urgent call to you?',
  ],
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

const HIGHLIGHT_EMISSIVE = 0xe88080

function disposeMaterialClone(material: Mesh['material']) {
  const list = Array.isArray(material) ? material : [material]
  for (const m of list) {
    m.dispose()
  }
}

function applySoftEmissiveToMaterial(material: Mesh['material']) {
  const list = Array.isArray(material) ? material : [material]
  for (const m of list) {
    if (
      'emissive' in m &&
      m.emissive &&
      'emissiveIntensity' in m &&
      typeof (m as MeshStandardMaterial).emissiveIntensity === 'number'
    ) {
      const emissiveMat = m as MeshStandardMaterial
      emissiveMat.emissive.setHex(HIGHLIGHT_EMISSIVE)
      emissiveMat.emissiveIntensity = 0.4
    }
  }
}

function useSelectedMeshEmissiveHighlight(
  scene: Group,
  selectedMeshUuid: string | null,
) {
  const selectionMaterialsRef = useRef<{
    mesh: Mesh
    originalMaterial: Mesh['material']
    highlightMaterial: Mesh['material']
  } | null>(null)

  useEffect(() => {
    const prev = selectionMaterialsRef.current
    if (prev) {
      const { mesh, originalMaterial, highlightMaterial } = prev
      mesh.material = originalMaterial
      disposeMaterialClone(highlightMaterial)
      selectionMaterialsRef.current = null
    }

    if (!selectedMeshUuid) return

    const target = scene.getObjectByProperty('uuid', selectedMeshUuid)
    if (!(target instanceof Mesh)) return

    const orig = target.material
    const cloned = Array.isArray(orig)
      ? orig.map((m) => m.clone())
      : orig.clone()

    applySoftEmissiveToMaterial(cloned)
    target.material = cloned
    selectionMaterialsRef.current = {
      mesh: target,
      originalMaterial: orig,
      highlightMaterial: cloned,
    }

    return () => {
      const cur = selectionMaterialsRef.current
      if (!cur) return
      const { mesh, originalMaterial, highlightMaterial } = cur
      mesh.material = originalMaterial
      disposeMaterialClone(highlightMaterial)
      selectionMaterialsRef.current = null
    }
  }, [scene, selectedMeshUuid])
}

type HeartMeshProps = {
  onSelect: (payload: MeshSelectPayload | null) => void
  selectedMeshUuid: string | null
  onSelectMesh: Dispatch<SetStateAction<string | null>>
}

function HeartMesh({
  onSelect,
  selectedMeshUuid,
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
  useSelectedMeshEmissiveHighlight(gltf.scene, selectedMeshUuid)

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
          const payload = meshSelectPayloadFromName(mesh.name)
          console.log(
            `CLICKED: ${mesh.name} → resolved to: ${payload.label}`,
          )
          onSelectMesh(mesh.uuid)
          onSelect(payload)
          e.stopPropagation()
        }}
      >
        <group ref={spinRef}>
          <primitive object={gltf.scene} />
          <HeartCallouts anchors={calloutAnchors} />
        </group>
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
  const [selectedMeshUuid, setSelectedMeshUuid] = useState<string | null>(null)

  const handlePointerMissed = () => {
    setSelectedMeshUuid(null)
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
            selectedMeshUuid={selectedMeshUuid}
            onSelectMesh={setSelectedMeshUuid}
          />
        </Suspense>
        <AdaptiveDpr />
        <OrbitControls makeDefault />
      </Canvas>
    </div>
  )
}
