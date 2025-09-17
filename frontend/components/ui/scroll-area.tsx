'use client'

import * as React from 'react'

export type ScrollAreaProps = React.HTMLAttributes<HTMLDivElement> & {
  children?: React.ReactNode
}

export function ScrollArea({ className = '', children, style, ...props }: ScrollAreaProps) {
  return (
    <div
      className={`overflow-y-auto ${className}`}
      style={{ maxHeight: '24rem', ...style }}
      {...props}
    >
      {children}
    </div>
  )
}

export default ScrollArea



