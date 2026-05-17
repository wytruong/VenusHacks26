import {
  Suspense,
  type RefObject,
  useEffect,
  useRef,
  useState,
} from 'react'
import { Group, Vector3 } from 'three'
import type { OrbitControls as OrbitControlsImpl } from 'three-stdlib'
import { Canvas, useFrame, useThree } from '@react-three/fiber'
import { AdaptiveDpr, Center, Html, OrbitControls, useCursor, useGLTF } from '@react-three/drei'

const MODEL_URL = '/heart-model/scene.quality.glb'

export type MeshSelectPayload = {
  label: string
  description: string
  doctorQuestions: readonly [string, string]
}

type HeartCalloutDef = {
  id: number
  label: string
  description: string
  position: [number, number, number]
  eye: [number, number, number]
}

type HeartFocusTarget = {
  target: [number, number, number]
  eye: [number, number, number]
}

type HeartCameraRigProps = {
  focusTarget: HeartFocusTarget | null
  controlsRef: RefObject<OrbitControlsImpl | null>
}

const HEART_CALLOUT_DEFS: HeartCalloutDef[] = [
  {
    id: 1,
    label: 'Ascending Aorta',
    description:
      'The first section of the aorta carries oxygen-rich blood from the left ventricle toward the body.',
    position: [0.08508526437789589, -0.16036335939257407, 0.3281038461716874],
    eye: [-14.1695327503, -60.7332914473, 24.029996349],
  },
  {
    id: 2,
    label: 'Ligamentum Arteriosum',
    description:
      'A small remnant of fetal circulation that once connected the pulmonary trunk and aortic arch.',
    position: [0.27285687964635075, 0.04837882970841356, 0.3610641468239272],
    eye: [26.753609884916727, -63.330727287004194, 75.91530797701509],
  },
  {
    id: 3,
    label: 'Pulmonary Trunk',
    description:
      'This vessel carries deoxygenated blood from the right ventricle toward the pulmonary arteries.',
    position: [0.27502088040656264, -0.05526585024858651, 0.32607506939414543],
    eye: [6.382912653980374, -32.90276907714171, 44.341114050137485],
  },
  {
    id: 4,
    label: 'Left Auricle',
    description:
      'A small pouch extending from the left atrium and representing part of the embryonic atrium.',
    position: [0.332230224443837, -0.009905507437994333, 0.09303287383175286],
    eye: [50.18380202357055, -28.322178742831017, 14.486128552474211],
  },
  {
    id: 5,
    label: 'Left Atrium',
    description:
      'The chamber that receives oxygenated blood from the lungs before passing it to the left ventricle.',
    position: [0.09859221210006816, 0.17041402564297947, -0.057191486632003186],
    eye: [32.539142304024196, 96.74446332318449, -1.3387121933179722],
  },
  {
    id: 6,
    label: 'Left Pulmonary Veins',
    description:
      'These veins return oxygenated blood from the left lung into the left atrium.',
    position: [0.28807147221104934, 0.13993399418935443, -0.030120282897583776],
    eye: [67.69573831320824, 76.42582936446514, 3.771230556287405],
  },
  {
    id: 7,
    label: 'Right Pulmonary Veins',
    description:
      'These veins return oxygenated blood from the right lung into the left atrium.',
    position: [-0.09659372819053315, 0.1458900064380451, -0.0323737521645583],
    eye: [13.189309246767014, 101.1201053411655, 3.802662522523793],
  },
  {
    id: 8,
    label: 'Right Atrium',
    description:
      'This chamber receives deoxygenated blood from the body and sends it toward the right ventricle.',
    position: [-0.1904807413535894, -0.05246078462336641, -0.12636695332798029],
    eye: [-75.5841711187767, 28.22168743311042, -11.6126202413856],
  },
  {
    id: 9,
    label: 'Right Auricle',
    description:
      'A small pouch extending from the right atrium and representing part of the embryonic atrium.',
    position: [-0.12569692983836778, -0.19053844456118513, 0.16720203637949538],
    eye: [-93.52455301553519, 6.301156791607418, 40.50789902616931],
  },
  {
    id: 10,
    label: 'Inferior Vena Cava',
    description:
      'This large vein brings deoxygenated blood from the lower body into the right atrium.',
    position: [-0.14418186712386732, -0.07766721504106483, -0.42453469799842714],
    eye: [-93.52721585440244, 40.4187372517252, -5.380388995020503],
  },
  {
    id: 11,
    label: 'Superior Vena Cava',
    description:
      'This large vein brings deoxygenated blood from the upper body into the right atrium.',
    position: [-0.08051384450591133, -0.004568782371385121, 0.40275292005125796],
    eye: [-58.44248491476928, -77.28368403128108, 32.887279881401305],
  },
  {
    id: 12,
    label: 'Right Ventricle',
    description:
      'This chamber pumps deoxygenated blood through the pulmonary valve toward the lungs.',
    position: [0.04341924946229208, -0.6295853112129862, -0.1318668849675993],
    eye: [4.112777796812117, -95.90948014943797, 35.75361083263108],
  },
  {
    id: 13,
    label: 'Left Ventricle',
    description:
      'This chamber pumps oxygenated blood through the aortic valve into the ascending aorta.',
    position: [0.3779762019042259, -0.3553407134080059, -0.4621615569887685],
    eye: [53.02104293976333, 54.33156853705336, -68.36790449549437],
  },
  {
    id: 14,
    label: 'Right Coronary Artery',
    description:
      'This artery branches from the ascending aorta and supplies blood to the right side of the heart.',
    position: [-0.08770446235290894, -0.3188565198440542, 0.09258853607763132],
    eye: [2.466230623129791, -3.0382767428985438, 43.51691736500667],
  },
  {
    id: 15,
    label: 'Left Coronary Artery',
    description:
      'This artery branches from the ascending aorta and divides into major vessels serving the left heart.',
    position: [0.2952827521980628, -0.08426246597541054, 0.15981067912460983],
    eye: [61.27780462733365, -29.230008050677462, 75.51486520235967],
  },
  {
    id: 16,
    label: 'Coronary Sinus',
    description:
      'This venous channel collects blood from cardiac veins and drains into the right atrium.',
    position: [0.1156862132430722, -0.002709348825158798, -0.32312622735061397],
    eye: [-17.702333907217604, 28.334546790996143, -57.55114182096676],
  },
  {
    id: 17,
    label: 'Great Cardiac Vein',
    description:
      'This cardiac vein runs with the coronary arteries and returns used blood from the heart muscle.',
    position: [0.3037301842959335, 0.012460053743057427, -0.11874414158210524],
    eye: [96.77301564063777, 79.03876859986521, -13.828418181189528],
  },
  {
    id: 18,
    label: 'Middle Cardiac Vein',
    description:
      'This cardiac vein drains the posterior heart surface toward the coronary sinus.',
    position: [0.05937715615916756, -0.20481080151469588, -0.43289900242368107],
    eye: [1.729273064419059, -0.06363184237172911, -102.17854268932014],
  },
  {
    id: 19,
    label: 'Small Cardiac Vein',
    description:
      'This cardiac vein helps return deoxygenated blood from the right side of the heart.',
    position: [-0.09545841831171291, -0.39974173799248747, -0.36384991129435423],
    eye: [-91.7556306006618, -26.483599377303843, -33.79330658435039],
  },
  {
    id: 20,
    label: 'Posterior Cardiac Vein',
    description:
      'This vein drains blood from the posterior wall of the left ventricle toward the coronary sinus.',
    position: [0.3343165163602777, -0.11750640777622014, -0.3543708380557144],
    eye: [45.85565443914214, 39.64758853819583, -81.19643105004684],
  },
]

const SKETCHFAB_MODEL_MATRIX = [
  0.9872612357139587, 0.049341931939125026, 0.1512635052204132, 0,
  0.15627101063728333, -0.12198609113693215, -0.980152428150177, 0,
  -0.02991057001054287, 0.9913045763969421, -0.12814284861087777, 0,
  0.028659891337156296, -0.02640748210251331, -0.012019101530313497, 1,
] as const

function toHeartModelSpace(position: [number, number, number]): [number, number, number] {
  const [x, y, z] = position
  const m = SKETCHFAB_MODEL_MATRIX
  return [
    m[0] * x + m[4] * y + m[8] * z + m[12],
    m[1] * x + m[5] * y + m[9] * z + m[13],
    m[2] * x + m[6] * y + m[10] * z + m[14],
  ]
}

function transformedDirection(
  from: [number, number, number],
  to: [number, number, number],
) {
  const start = toHeartModelSpace(from)
  const end = toHeartModelSpace(to)
  return new Vector3(
    start[0] - end[0],
    start[1] - end[1],
    start[2] - end[2],
  )
}

function HeartAnnotationMarker({
  anchor,
  selected,
  onSelectAnnotation,
  onAnnotationHover,
}: {
  anchor: HeartCalloutDef
  selected: boolean
  onSelectAnnotation: (def: HeartCalloutDef) => void
  onAnnotationHover: (hovered: boolean) => void
}) {
  const markerRef = useRef<Group>(null)
  const camera = useThree((state) => state.camera)
  const [frontFacing, setFrontFacing] = useState(true)
  const visible = selected || frontFacing

  useFrame(() => {
    const marker = markerRef.current
    if (!marker) return

    const markerPosition = new Vector3()
    marker.getWorldPosition(markerPosition)

    const outward = markerPosition.clone()
    if (outward.lengthSq() < 0.0001) return

    const cameraDirection = camera.position.clone().sub(markerPosition)
    const nextFrontFacing =
      outward.normalize().dot(cameraDirection.normalize()) > -0.12

    setFrontFacing((prev) => (prev === nextFrontFacing ? prev : nextFrontFacing))
  })

  return (
    <group ref={markerRef} key={anchor.id} position={toHeartModelSpace(anchor.position)}>
      <mesh
        visible={visible}
        onPointerOver={(e) => {
          if (!visible) return
          e.stopPropagation()
          onAnnotationHover(true)
        }}
        onPointerOut={(e) => {
          e.stopPropagation()
          onAnnotationHover(false)
        }}
        onClick={(e) => {
          if (!visible) return
          e.stopPropagation()
          onSelectAnnotation(anchor)
        }}
      >
        <sphereGeometry args={[selected ? 0.022 : 0.018, 18, 18]} />
        <meshBasicMaterial
          color={selected ? '#ffffff' : '#ffb3c1'}
          depthTest
          transparent
          opacity={selected ? 0.98 : 0.72}
        />
      </mesh>
      <Html
        center
        distanceFactor={selected ? 0.72 : 0.78}
        style={{
          opacity: visible ? 1 : 0,
          pointerEvents: visible ? 'auto' : 'none',
          transition: 'opacity 180ms ease',
          userSelect: 'none',
        }}
      >
        <button
          type="button"
          aria-label={`Select ${anchor.label}`}
          className={`flex h-7 w-7 items-center justify-center rounded-full border text-[11px] font-semibold leading-none shadow-[0_0_20px_rgba(255,112,145,0.34)] backdrop-blur-md ${
            selected
              ? 'border-white bg-white/90 text-[#2a0d12]'
              : 'border-white/40 bg-[#2a0d12]/70 text-rose-50'
          }`}
          onClick={(e) => {
            e.stopPropagation()
            onSelectAnnotation(anchor)
          }}
          onPointerEnter={() => onAnnotationHover(true)}
          onPointerLeave={() => onAnnotationHover(false)}
        >
          {anchor.id}
        </button>
      </Html>
    </group>
  )
}

function HeartCallouts({
  selectedAnnotationId,
  onSelectAnnotation,
  onAnnotationHover,
}: {
  selectedAnnotationId: number | null
  onSelectAnnotation: (def: HeartCalloutDef) => void
  onAnnotationHover: (hovered: boolean) => void
}) {
  return HEART_CALLOUT_DEFS.map((anchor) => {
    const selected = anchor.id === selectedAnnotationId

    return (
      <HeartAnnotationMarker
        key={anchor.id}
        anchor={anchor}
        selected={selected}
        onSelectAnnotation={onSelectAnnotation}
        onAnnotationHover={onAnnotationHover}
      />
    )
  })
}

function annotationToPayload(annotation: HeartCalloutDef): MeshSelectPayload {
  return {
    label: annotation.label,
    description: annotation.description,
    doctorQuestions: [
      `Is my ${annotation.label.toLowerCase()} under extra strain during pregnancy?`,
      `What symptoms related to this area should make me call you?`,
    ],
  }
}

function HeartCameraRig({ focusTarget, controlsRef }: HeartCameraRigProps) {
  const camera = useThree((state) => state.camera)
  const targetRef = useRef(new Vector3(0, 0, 0))
  const cameraRef = useRef(new Vector3(0, 0.08, 1.35))

  useEffect(() => {
    if (!focusTarget) return

    const target = toHeartModelSpace(focusTarget.target)
    const direction = transformedDirection(focusTarget.eye, focusTarget.target)
    const distance = 1.24

    if (direction.lengthSq() === 0) {
      direction.set(0, 0, 1)
    }

    const targetVector = new Vector3(...target)
    targetRef.current.copy(targetVector)
    cameraRef.current.copy(targetVector).add(direction.normalize().multiplyScalar(distance))
  }, [focusTarget])

  useFrame((_, delta) => {
    if (!focusTarget) return

    const controls = controlsRef.current
    const alpha = 1 - Math.exp(-delta * 4.2)

    camera.position.lerp(cameraRef.current, alpha)
    controls?.target.lerp(targetRef.current, alpha)
    controls?.update()
  })

  return null
}

type HeartMeshProps = {
  onSelect: (payload: MeshSelectPayload | null) => void
  onFocusChange: (focus: HeartFocusTarget | null) => void
  selectedAnnotationId: number | null
  onSelectAnnotationId: (id: number | null) => void
}

function HeartMesh({
  onSelect,
  onFocusChange,
  selectedAnnotationId,
  onSelectAnnotationId,
}: HeartMeshProps) {
  const gltf = useGLTF(MODEL_URL)
  const spinRef = useRef<Group>(null)
  const [cursorHover, setCursorHover] = useState(false)
  useCursor(cursorHover)

  useFrame((state, delta) => {
    const spin = spinRef.current
    if (!spin) return
    if (selectedAnnotationId !== null) return
    const elapsed = state.clock.elapsedTime
    spin.rotation.y += delta * (0.2 + Math.sin(elapsed * 0.5) * 0.08)
    spin.position.y = Math.sin(elapsed * 0.8) * 0.05
  })

  return (
    <Center ref={spinRef}>
      <group>
        <primitive object={gltf.scene} />
        <HeartCallouts
          selectedAnnotationId={selectedAnnotationId}
          onAnnotationHover={setCursorHover}
          onSelectAnnotation={(annotation) => {
            onSelectAnnotationId(annotation.id)
            onFocusChange({
              target: annotation.position,
              eye: annotation.eye,
            })
            onSelect(annotationToPayload(annotation))
          }}
        />
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
  const [selectedAnnotationId, setSelectedAnnotationId] = useState<number | null>(null)
  const [focusTarget, setFocusTarget] = useState<HeartFocusTarget | null>(null)
  const controlsRef = useRef<OrbitControlsImpl | null>(null)

  const handlePointerMissed = () => {
    setSelectedAnnotationId(null)
    setFocusTarget(null)
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
            onFocusChange={setFocusTarget}
            selectedAnnotationId={selectedAnnotationId}
            onSelectAnnotationId={setSelectedAnnotationId}
          />
        </Suspense>
        <HeartCameraRig focusTarget={focusTarget} controlsRef={controlsRef} />
        <AdaptiveDpr />
        <OrbitControls
          ref={controlsRef}
          makeDefault
          enableDamping
          enablePan={false}
          target={[0, 0, 0]}
        />
      </Canvas>
    </div>
  )
}
