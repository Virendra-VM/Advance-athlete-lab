import { cardShellClass } from '../../utils/statusColors'

export default function Card({ children, className = '' }) {
  return (
    <div className={`${cardShellClass} ${className}`}>
      {children}
    </div>
  )
}
