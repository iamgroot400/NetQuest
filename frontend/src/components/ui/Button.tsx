import type { ButtonHTMLAttributes, ReactNode } from 'react'

type Variant = 'default' | 'primary' | 'ghost' | 'danger'
type Size = 'sm' | 'md'

const VARIANTS: Record<Variant, string> = {
  default:
    'bg-raised text-ink border-line hover:bg-line hover:border-ink-faint disabled:hover:bg-raised',
  primary:
    'bg-accent/15 text-accent border-accent/40 hover:bg-accent/25 disabled:hover:bg-accent/15',
  ghost:
    'bg-transparent text-ink-dim border-transparent hover:bg-raised hover:text-ink',
  danger: 'bg-bad/10 text-bad border-bad/30 hover:bg-bad/20 disabled:hover:bg-bad/10',
}

const SIZES: Record<Size, string> = {
  sm: 'h-7 px-2 text-xs gap-1.5',
  md: 'h-9 px-3 text-sm gap-2',
}

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant
  size?: Size
  children?: ReactNode
}

export function Button({
  variant = 'default',
  size = 'md',
  className = '',
  children,
  ...props
}: ButtonProps) {
  return (
    <button
      type="button"
      {...props}
      className={`inline-flex items-center justify-center rounded-md border font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-40 ${VARIANTS[variant]} ${SIZES[size]} ${className}`}
    >
      {children}
    </button>
  )
}

interface IconButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  label: string
  variant?: Variant
  children: ReactNode
}

export function IconButton({
  label,
  variant = 'ghost',
  className = '',
  children,
  ...props
}: IconButtonProps) {
  return (
    <button
      type="button"
      aria-label={label}
      title={label}
      {...props}
      className={`inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-md border transition-colors disabled:cursor-not-allowed disabled:opacity-40 ${VARIANTS[variant]} ${className}`}
    >
      {children}
    </button>
  )
}
