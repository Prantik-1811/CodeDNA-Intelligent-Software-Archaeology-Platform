import type { ComponentType } from "react"

export interface ProfileCardProps {
  avatarUrl?: string
  iconUrl?: string
  miniAvatarUrl?: string
  name?: string
  title?: string
  handle?: string
  status?: string
  statusColor?: string
  contactText?: string
  showUserInfo?: boolean
  onContactClick?: () => void
  theme?: "dark" | "light"
  backdropColor?: string
  radius?: number
  holo?: number
  glare?: number
  enableTilt?: boolean
  tiltStrength?: number
  parallax?: number
  enableMobileTilt?: boolean
  mobileTiltSensitivity?: number
  intro?: boolean
  className?: string
}

declare const ProfileCard: ComponentType<ProfileCardProps>
export default ProfileCard
