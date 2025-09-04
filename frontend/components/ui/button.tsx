import * as React from "react"
import { Slot } from "@radix-ui/react-slot"
import { cva, type VariantProps } from "class-variance-authority"
import { cn } from "@/lib/utils"

const buttonVariants = cva(
  "inline-flex items-center justify-center whitespace-nowrap rounded-lg font-medium transition-all duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50",
  {
    variants: {
      variant: {
        default: "cylvy-gradient-primary text-white shadow hover:scale-105 hover:shadow-lg focus:ring-[rgb(229,24,72)]",
        cylvy: "cylvy-gradient-primary text-white shadow hover:scale-105 hover:shadow-lg focus:ring-[rgb(229,24,72)]",
        destructive: "bg-error text-white shadow-sm hover:bg-error/90",
        outline: "border-2 border-cylvy-grape text-cylvy-grape hover:bg-cylvy-grape hover:text-white focus:ring-[rgb(136,6,191)]",
        secondary: "border-2 border-cylvy-grape text-cylvy-grape hover:bg-cylvy-grape hover:text-white focus:ring-[rgb(136,6,191)]",
        ghost: "text-cylvy-amaranth hover:bg-[rgb(229,24,72)]/10 focus:ring-[rgb(229,24,72)]",
        link: "text-cylvy-amaranth underline-offset-4 hover:underline",
      },
      size: {
        default: "h-10 px-6 py-2",
        sm: "h-8 rounded-md px-4 text-sm",
        lg: "h-12 rounded-lg px-8 text-lg",
        icon: "h-10 w-10",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  }
)

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : "button"
    return (
      <Comp
        className={cn(buttonVariants({ variant, size, className }))}
        ref={ref}
        {...props}
      />
    )
  }
)
Button.displayName = "Button"

export { Button, buttonVariants }
