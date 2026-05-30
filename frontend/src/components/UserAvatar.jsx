export default function UserAvatar({ letter, name, size = 'md' }) {
  const display = (letter || name?.[0] || '?').toUpperCase()
  const sizes = {
    sm: 'h-8 w-8 text-sm',
    md: 'h-10 w-10 text-base',
    lg: 'h-16 w-16 text-2xl',
    xl: 'h-24 w-24 text-4xl',
  }

  return (
    <div
      className={`flex shrink-0 items-center justify-center rounded-full bg-sage font-bold text-white ${sizes[size] || sizes.md}`}
      title={name || 'Profile'}
    >
      {display}
    </div>
  )
}
