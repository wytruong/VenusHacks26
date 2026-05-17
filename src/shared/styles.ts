import type { CSSProperties } from 'react'

export const dmSans = '"DM Sans", system-ui, sans-serif'

export const glassPillButton =
  'rounded-full border border-white/20 bg-white/[0.08] px-6 py-3 text-sm font-normal text-[#FDF0F0] shadow-[0_4px_24px_rgba(255,255,255,0.06)] backdrop-blur-[12px] transition-[background-color,box-shadow] duration-700 ease-out hover:bg-white/[0.15] hover:shadow-[0_4px_24px_rgba(255,255,255,0.06),0_0_32px_rgba(255,255,255,0.14)] md:text-[0.9375rem]'

export const editProfilePillButton =
  'rounded-full border border-[#F4C2C2] bg-white/[0.08] px-3 py-1.5 text-[11px] font-normal text-[#9B7B7B] shadow-[0_4px_24px_rgba(255,255,255,0.06)] backdrop-blur-[12px] transition-[background-color,box-shadow] duration-300 hover:bg-white/[0.12]'

export const glassTogglePill =
  'rounded-full border border-[#F4C2C2] px-5 py-2 text-xs font-normal text-[#FDF0F0] shadow-[0_4px_24px_rgba(255,255,255,0.06)] backdrop-blur-[12px] transition-[background-color] duration-300'

export const glassFieldCardStyle: CSSProperties = {
  backdropFilter: 'blur(12px)',
  WebkitBackdropFilter: 'blur(12px)',
  backgroundColor: 'rgba(255,255,255,0.08)',
  border: '1px solid #F4C2C2',
  borderRadius: 12,
}

export const glassNumberInputStyle: CSSProperties = {
  marginTop: 8,
  width: '100%',
  border: 'none',
  outline: 'none',
  background: 'transparent',
  color: '#FDF0F0',
  fontFamily: dmSans,
  fontSize: 15,
}

export const doctorNoteUploadZoneStyle: CSSProperties = {
  width: '100%',
  maxWidth: 400,
  height: 250,
  borderRadius: 16,
  border: '1px dashed #F4C2C2',
  backdropFilter: 'blur(12px)',
  WebkitBackdropFilter: 'blur(12px)',
  backgroundColor: 'rgba(255,255,255,0.05)',
}

export const ecgUploadZoneStyle: CSSProperties = {
  width: '100%',
  maxWidth: 400,
  height: 200,
  borderRadius: 16,
  border: '1px dashed #F4C2C2',
  backdropFilter: 'blur(12px)',
  WebkitBackdropFilter: 'blur(12px)',
  backgroundColor: 'rgba(255,255,255,0.05)',
}

export const profilePanelGlassInputStyle: CSSProperties = {
  width: '100%',
  boxSizing: 'border-box',
  border: '1px solid #F4C2C2',
  borderRadius: 10,
  backgroundColor: 'rgba(255,255,255,0.08)',
  color: '#FDF0F0',
  fontFamily: dmSans,
  fontSize: 11,
  padding: '8px 10px',
  outline: 'none',
}
