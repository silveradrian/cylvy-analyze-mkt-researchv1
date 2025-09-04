import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"
import { cn } from "@/lib/utils"

const badgeVariants = cva(
  "inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-offset-2",
  {
    variants: {
      variant: {
        default: "cylvy-badge-primary border border-[rgb(229,24,72)]/20",
        primary: "cylvy-badge-primary border border-[rgb(229,24,72)]/20", 
        secondary: "bg-[rgb(136,6,191)]/10 text-[rgb(136,6,191)] border border-[rgb(136,6,191)]/20",
        success: "cylvy-badge-success border border-green-200",
        warning: "cylvy-badge-warning border border-yellow-200", 
        error: "cylvy-badge-error border border-red-200",
        outline: "border border-gray-300 text-gray-700 hover:bg-gray-50",
        dark: "bg-cylvy-midnight text-white border border-cylvy-slate",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  }
)

export interface BadgeProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof badgeVariants> {}

function Badge({ className, variant, ...props }: BadgeProps) {
  return (
    <div className={cn(badgeVariants({ variant }), className)} {...props} />
  )
}

export { Badge, badgeVariants }
