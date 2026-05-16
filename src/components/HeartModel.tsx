import { Suspense, useCallback, useEffect, useRef, useState } from 'react'
import {
  Color,
  type Group,
  type Material,
  Mesh,
  MeshBasicMaterial,
  MeshLambertMaterial,
  MeshPhongMaterial,
  MeshPhysicalMaterial,
  MeshStandardMaterial,
} from 'three'
import { Canvas, useFrame } from '@react-three/fiber'
import { Center, OrbitControls, useCursor, useGLTF } from '@react-three/drei'

const MODEL_URL = '/heart-model/scene.gltf'

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

function cloneMaterial(m: Material | Material[]): Material | Material[] {
  return Array.isArray(m) ? m.map((x) => x.clone()) : m.clone()
}

function glowifyMaterial(mat: Material): Material {
  const c = mat.clone()
  if (
    c instanceof MeshStandardMaterial ||
    c instanceof MeshPhysicalMaterial
  ) {
    c.emissive.set('#E88080')
    c.emissiveIntensity = 0.6
    return c
  }
  if (c instanceof MeshLambertMaterial || c instanceof MeshPhongMaterial) {
    c.emissive.set('#E88080')
    c.emissiveIntensity = 0.6
    return c
  }
  if (c instanceof MeshBasicMaterial) {
    const col = c.color.clone()
    col.lerp(new Color('#E88080'), 0.35)
    c.color.copy(col)
    return c
  }
  return c
}

function restoreMesh(mesh: Mesh, originals: Map<Mesh, Material | Material[]>) {
  const orig = originals.get(mesh)
  if (!orig) return
  mesh.material = cloneMaterial(orig)
}

function applyGlowMaterial(
  mesh: Mesh,
  originals: Map<Mesh, Material | Material[]>,
) {
  if (!originals.has(mesh)) {
    originals.set(mesh, cloneMaterial(mesh.material))
  }
  const template = originals.get(mesh)!
  const branch = cloneMaterial(template)
  mesh.material = Array.isArray(branch)
    ? branch.map(glowifyMaterial)
    : glowifyMaterial(branch as Material)
}

type HeartMeshProps = {
  selected: Mesh | null
  setSelected: (m: Mesh | null) => void
  onSelect: (payload: MeshSelectPayload | null) => void
}

function HeartMesh({ selected, setSelected, onSelect }: HeartMeshProps) {
  const gltf = useGLTF(MODEL_URL)
  const spinRef = useRef<Group>(null)
  const originalsRef = useRef(new Map<Mesh, Material | Material[]>())
  const hoverRef = useRef<Mesh | null>(null)
  const glowingRef = useRef<Mesh | null>(null)
  const [cursorHover, setCursorHover] = useState(false)
  useCursor(cursorHover)

  const syncGlow = useCallback((hovered: Mesh | null, sel: Mesh | null) => {
    const target = hovered ?? sel
    if (glowingRef.current === target) return
    if (glowingRef.current) {
      restoreMesh(glowingRef.current, originalsRef.current)
    }
    glowingRef.current = target
    if (target) {
      applyGlowMaterial(target, originalsRef.current)
    }
  }, [])

  useEffect(() => {
    syncGlow(hoverRef.current, selected)
  }, [selected, syncGlow])

  useEffect(() => {
    const scene = gltf.scene
    const originalsMap = originalsRef.current
    return () => {
      scene.traverse((obj) => {
        if ((obj as Mesh).isMesh) {
          restoreMesh(obj as Mesh, originalsMap)
        }
      })
      originalsMap.clear()
      glowingRef.current = null
      hoverRef.current = null
    }
  }, [gltf.scene])

  useFrame((_, delta) => {
    const spin = spinRef.current
    if (!spin) return
    const now = Date.now()
    spin.rotation.y += delta * (0.2 + Math.sin(now * 0.0005) * 0.08)
    spin.position.y = Math.sin(now * 0.0008) * 0.05
  })

  return (
    <Center>
      <group
        onPointerMove={(e) => {
          const hit = e.intersections.find((i) => (i.object as Mesh).isMesh)
          const mesh = hit?.object instanceof Mesh ? hit.object : null
          if (mesh !== hoverRef.current) {
            hoverRef.current = mesh
            setCursorHover(mesh !== null)
            syncGlow(mesh, selected)
          }
        }}
        onPointerLeave={() => {
          hoverRef.current = null
          setCursorHover(false)
          syncGlow(null, selected)
        }}
        onClick={(e) => {
          const hit = e.intersections.find((i) => (i.object as Mesh).isMesh)
          if (!hit || !(hit.object instanceof Mesh)) return
          const mesh = hit.object
          const payload = meshSelectPayloadFromName(mesh.name)
          setSelected(mesh)
          onSelect(payload)
          e.stopPropagation()
        }}
      >
        <group ref={spinRef}>
          <primitive object={gltf.scene} />
        </group>
      </group>
    </Center>
  )
}

useGLTF.preload(MODEL_URL)

type HeartModelProps = {
  onSelect: (payload: MeshSelectPayload | null) => void
}

export default function HeartModel({ onSelect }: HeartModelProps) {
  const [selected, setSelected] = useState<Mesh | null>(null)

  const handlePointerMissed = () => {
    setSelected(null)
    onSelect(null)
  }

  return (
    <div className="fixed inset-0 h-screen w-screen bg-[#1a0a0a]">
      <Canvas
        className="h-full w-full touch-none"
        camera={{ position: [0, 0.08, 1.35], fov: 42 }}
        gl={{ antialias: true }}
        onPointerMissed={handlePointerMissed}
      >
        <color attach="background" args={['#1a0a0a']} />
        <ambientLight intensity={1.8} />
        <pointLight
          color="#FFB3B3"
          position={[1.25, 1.6, 2.2]}
          intensity={1.15}
          distance={14}
          decay={2}
        />
        <pointLight color="#FFB3B3" intensity={4} position={[5, 5, 5]} />
        <pointLight color="#ffffff" intensity={3} position={[-5, 3, 5]} />
        <directionalLight
          color="#ffffff"
          intensity={2}
          position={[0, 5, 10]}
        />
        <Suspense fallback={null}>
          <HeartMesh
            selected={selected}
            setSelected={setSelected}
            onSelect={onSelect}
          />
        </Suspense>
        <OrbitControls enableDamping makeDefault />
      </Canvas>
    </div>
  )
}
