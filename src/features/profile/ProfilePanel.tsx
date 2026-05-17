import { type ChangeEvent, type CSSProperties, type RefObject } from 'react'
import { dmSans, profilePanelGlassInputStyle } from '../../shared/styles'

function ProfileCameraGlyph({
  className,
  style,
}: {
  className?: string
  style?: CSSProperties
}) {
  return (
    <svg
      className={className}
      style={style}
      width={20}
      height={20}
      viewBox="0 0 24 24"
      fill="currentColor"
      aria-hidden
    >
      <path d="M9 4h6l1.83 2H20a2 2 0 012 2v10a2 2 0 01-2 2H4a2 2 0 01-2-2V8a2 2 0 012-2h3.17L9 4zm3 13a4 4 0 100-8 4 4 0 000 8z" />
    </svg>
  )
}

type ProfilePanelProps = {
  profileAvatarInputRef: RefObject<HTMLInputElement | null>
  profileAvatarUrl: string | null
  onProfileAvatarChange: (e: ChangeEvent<HTMLInputElement>) => void
  pregnancyMode: 'prenatal' | 'postpartum' | null
  profileDisplayName: string
  setProfileDisplayName: (value: string) => void
  profileAge: string
  setProfileAge: (value: string) => void
  profileWeeksPregnant: string
  setProfileWeeksPregnant: (value: string) => void
  profileWeeksPostpartum: string
  setProfileWeeksPostpartum: (value: string) => void
  profileMedications: string
  setProfileMedications: (value: string) => void
  profileAllergies: string
  setProfileAllergies: (value: string) => void
  profileLatestVisit: string
  setProfileLatestVisit: (value: string) => void
}

export function ProfilePanel({
  profileAvatarInputRef,
  profileAvatarUrl,
  onProfileAvatarChange,
  pregnancyMode,
  profileDisplayName,
  setProfileDisplayName,
  profileAge,
  setProfileAge,
  profileWeeksPregnant,
  setProfileWeeksPregnant,
  profileWeeksPostpartum,
  setProfileWeeksPostpartum,
  profileMedications,
  setProfileMedications,
  profileAllergies,
  setProfileAllergies,
  profileLatestVisit,
  setProfileLatestVisit,
}: ProfilePanelProps) {
  return (
    <aside
      className="pointer-events-auto fixed left-0 top-0 z-[34] hidden h-full min-h-0 w-[220px] flex-col overflow-hidden md:flex"
      style={{
        backdropFilter: 'blur(16px)',
        WebkitBackdropFilter: 'blur(16px)',
        backgroundColor: 'rgba(255,255,255,0.06)',
        borderRight: '1px solid rgba(255,255,255,0.1)',
        fontFamily: dmSans,
      }}
      aria-label="Profile"
    >
      <div className="flex min-h-0 flex-1 flex-col">
        <div className="min-h-0 flex-1 overflow-y-auto overscroll-y-contain px-3 pt-16">
          <input
            ref={profileAvatarInputRef}
            type="file"
            accept="image/*"
            className="sr-only"
            aria-hidden
            tabIndex={-1}
            onChange={onProfileAvatarChange}
          />
          <button
            type="button"
            className="mx-auto flex h-[56px] w-[56px] shrink-0 items-center justify-center overflow-hidden rounded-full border-2 border-[#F4C2C2] bg-white/[0.10] outline-none transition-opacity hover:opacity-95 focus-visible:ring-2 focus-visible:ring-[#F4C2C2]/60"
            aria-label="Upload profile photo"
            onClick={() => profileAvatarInputRef.current?.click()}
          >
            {profileAvatarUrl ? (
              <img
                src={profileAvatarUrl}
                alt=""
                className="h-full w-full object-cover"
                draggable={false}
              />
            ) : (
              <ProfileCameraGlyph className="text-[#9B7B7B]" />
            )}
          </button>

          <input
            type="text"
            value={profileDisplayName}
            onChange={(e) => setProfileDisplayName(e.target.value)}
            placeholder="Your name"
            className="mt-4 placeholder:text-[#D4B8B8]"
            style={profilePanelGlassInputStyle}
          />

          <input
            type="number"
            inputMode="numeric"
            min={0}
            value={profileAge}
            onChange={(e) => setProfileAge(e.target.value)}
            placeholder="Age"
            className="mt-2 placeholder:text-[#D4B8B8] tabular-nums"
            style={profilePanelGlassInputStyle}
          />

          {pregnancyMode === 'prenatal' ? (
            <input
              type="number"
              inputMode="numeric"
              min={0}
              value={profileWeeksPregnant}
              onChange={(e) => setProfileWeeksPregnant(e.target.value)}
              placeholder="e.g. 28 weeks"
              className="mt-2 placeholder:text-[#D4B8B8] tabular-nums"
              style={profilePanelGlassInputStyle}
            />
          ) : null}

          {pregnancyMode === 'postpartum' ? (
            <input
              type="number"
              inputMode="numeric"
              min={0}
              value={profileWeeksPostpartum}
              onChange={(e) => setProfileWeeksPostpartum(e.target.value)}
              placeholder="e.g. 6 weeks"
              className="mt-2 placeholder:text-[#D4B8B8] tabular-nums"
              style={profilePanelGlassInputStyle}
            />
          ) : null}

          <div
            className="mb-1.5 mt-4 font-normal uppercase tracking-[0.14em] text-[#F4C2C2]"
            style={{ fontSize: 10 }}
          >
            Current medications
          </div>
          <textarea
            value={profileMedications}
            onChange={(e) => setProfileMedications(e.target.value)}
            placeholder="List any medications you're taking"
            rows={2}
            className="placeholder:text-[#D4B8B8]"
            style={{
              ...profilePanelGlassInputStyle,
              height: 60,
              minHeight: 60,
              resize: 'none',
            }}
          />

          <div
            className="mb-1.5 mt-3 font-normal uppercase tracking-[0.14em] text-[#F4C2C2]"
            style={{ fontSize: 10 }}
          >
            Allergies
          </div>
          <textarea
            value={profileAllergies}
            onChange={(e) => setProfileAllergies(e.target.value)}
            placeholder="List any known allergies"
            rows={2}
            className="placeholder:text-[#D4B8B8]"
            style={{
              ...profilePanelGlassInputStyle,
              height: 40,
              minHeight: 40,
              resize: 'none',
            }}
          />

          <div
            className="mb-1.5 mt-3 font-normal uppercase tracking-[0.14em] text-[#F4C2C2]"
            style={{ fontSize: 10 }}
          >
            Latest doctor visit
          </div>
          <textarea
            value={profileLatestVisit}
            onChange={(e) => setProfileLatestVisit(e.target.value)}
            placeholder="Notes from your last appointment"
            rows={2}
            className="placeholder:text-[#D4B8B8]"
            style={{
              ...profilePanelGlassInputStyle,
              height: 60,
              minHeight: 60,
              resize: 'none',
            }}
          />
        </div>

        <footer className="mt-auto shrink-0 px-3 pb-6 pt-4 text-center font-normal leading-snug text-[#9B7B7B]">
          <div style={{ fontFamily: dmSans, fontSize: 9 }}>VenusHacks 2026</div>
          <div
            className="mt-0.5"
            style={{ fontFamily: dmSans, fontSize: 9 }}
          >
            My Truong · Mary Nguyen · Harry Tran · Ben Nguyen
          </div>
        </footer>
      </div>
    </aside>
  )
}
