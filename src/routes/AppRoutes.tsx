import type { ReactNode } from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'
import { ROUTE_PATHS } from './paths'

type AppRoutesProps = {
  landing: ReactNode
  onboarding: ReactNode
  riskProfile: ReactNode
  heart: ReactNode
  ecgUpload: ReactNode
  doctorNoteUpload: ReactNode
}

export function AppRoutes({
  landing,
  onboarding,
  riskProfile,
  heart,
  ecgUpload,
  doctorNoteUpload,
}: AppRoutesProps) {
  return (
    <Routes>
      <Route path={ROUTE_PATHS.landing} element={landing} />
      <Route path={ROUTE_PATHS.onboarding} element={onboarding} />
      <Route path={ROUTE_PATHS.riskProfile} element={riskProfile} />
      <Route path={ROUTE_PATHS.heart} element={heart} />
      <Route path={ROUTE_PATHS.ecgUpload} element={ecgUpload} />
      <Route path={ROUTE_PATHS.doctorNoteUpload} element={doctorNoteUpload} />
      <Route path="*" element={<Navigate to={ROUTE_PATHS.landing} replace />} />
    </Routes>
  )
}
