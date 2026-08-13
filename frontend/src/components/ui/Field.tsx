import type { InputHTMLAttributes, ReactNode } from 'react'

interface FieldProps {
  label: string
  hint?: ReactNode
  error?: string | null
  children: ReactNode
}

export function Field({ label, hint, error, children }: FieldProps) {
  return (
    <label className="block">
      <span className="mb-1 flex items-baseline justify-between gap-2">
        <span className="text-[11px] font-medium tracking-wide text-ink-dim uppercase">
          {label}
        </span>
        {hint ? <span className="text-[11px] text-ink-faint">{hint}</span> : null}
      </span>
      {children}
      {error ? <span className="mt-1 block text-xs text-bad">{error}</span> : null}
    </label>
  )
}

interface TextInputProps extends InputHTMLAttributes<HTMLInputElement> {
  invalid?: boolean
}

export function TextInput({ invalid, className = '', ...props }: TextInputProps) {
  return (
    <input
      {...props}
      aria-invalid={invalid || undefined}
      className={`h-9 w-full rounded-md border bg-surface px-2.5 font-mono text-sm text-ink transition-colors placeholder:text-ink-faint focus:border-accent focus:outline-none disabled:opacity-50 ${
        invalid ? 'border-bad' : 'border-line'
      } ${className}`}
    />
  )
}

export function SectionTitle({ children }: { children: ReactNode }) {
  return (
    <h3 className="mb-2 text-[11px] font-semibold tracking-widest text-ink-faint uppercase">
      {children}
    </h3>
  )
}

export function Empty({ children }: { children: ReactNode }) {
  return (
    <p className="px-1 py-6 text-center text-xs leading-relaxed text-ink-faint">
      {children}
    </p>
  )
}
