import { useLayoutEffect, useRef } from 'react'

/** Announce submission errors and focus the field that needs attention. */
export function FormError({ id, message, fieldId, className }: {
  id: string
  message: string
  fieldId?: string
  className: string
}) {
  const ref = useRef<HTMLParagraphElement>(null)
  useLayoutEffect(() => {
    const field = fieldId ? document.getElementById(fieldId) : null
    ;(field ?? ref.current)?.focus()
  }, [message, fieldId])
  return <p ref={ref} id={id} className={className} role="alert" tabIndex={-1}>{message}</p>
}
