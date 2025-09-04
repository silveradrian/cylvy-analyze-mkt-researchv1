# Cylvy Design System Brief

**Design System for Data Analytics and Business Intelligence Applications**

---

## 🎨 Brand Identity

### Primary Brand Colors
- **Cylvy Amaranth**: `#E51848` (Primary action color)
- **Cylvy Grape**: `#8806BF` (Secondary accent)
- **Cylvy Midnight**: `#1A1A2E` (Dark background)
- **Cylvy Slate**: `#16213E` (Card backgrounds)

### Brand Gradients
```css
--gradient-primary: linear-gradient(135deg, #E51848 0%, #8806BF 100%)
--gradient-dark: linear-gradient(135deg, #1A1A2E 0%, #16213E 100%)
```

### Logo Usage
- **Primary Logo**: SVG format with Cylvy wordmark
- **Symbol Only**: Abstract geometric mark (two dots pattern)
- **Partner Integration**: nCino logo integration for co-branded applications

---

## 🎯 Design Philosophy

### Core Principles
1. **Data-Centric**: Visual hierarchy that prioritizes data clarity and insights
2. **Professional Authority**: Clean, sophisticated aesthetic for enterprise users
3. **Gradient-Forward**: Strategic use of brand gradients for visual interest
4. **Dark-First**: Optimized for extended data analysis sessions
5. **Interactive Excellence**: Smooth transitions and hover states

### Visual Language
- **Modern Corporate**: Professional yet approachable
- **High Contrast**: Excellent readability for data-heavy interfaces
- **Subtle Motion**: Purposeful animations that enhance UX
- **Card-Based Layout**: Modular content organization

---

## 🎨 Color System

### Primary Palette
```css
/* Brand Colors (RGB values for Tailwind) */
--cylvy-amaranth: 229 24 72;     /* #E51848 */
--cylvy-grape: 136 6 191;        /* #8806BF */
--cylvy-midnight: 26 26 46;      /* #1A1A2E */
--cylvy-slate: 22 33 62;         /* #16213E */
```

### Semantic Colors
```css
--color-success: 16 185 129;     /* #10B981 */
--color-warning: 245 158 11;     /* #F59E0B */
--color-error: 239 68 68;        /* #EF4444 */
--color-info: 59 130 246;        /* #3B82F6 */
```

### Neutral Scale
```css
--color-gray-50: 249 250 251;    /* Light mode backgrounds */
--color-gray-100: 243 244 246;
--color-gray-200: 229 231 235;   /* Borders */
--color-gray-300: 209 213 219;
--color-gray-400: 156 163 175;   /* Placeholder text */
--color-gray-500: 107 114 128;   /* Muted text */
--color-gray-600: 75 85 99;
--color-gray-700: 55 65 81;      /* Dark borders */
--color-gray-800: 31 41 55;      /* Dark cards */
--color-gray-900: 17 24 39;      /* Dark text */
```

---

## 📝 Typography

### Font Stack
```css
--font-primary: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
--font-mono: 'JetBrains Mono', 'Fira Code', monospace;
```

### Type Scale
- **4xl**: 2.25rem (36px) - Hero headings
- **3xl**: 1.875rem (30px) - Page titles
- **2xl**: 1.5rem (24px) - Section headings
- **xl**: 1.25rem (20px) - Card titles
- **lg**: 1.125rem (18px) - Subheadings
- **base**: 1rem (16px) - Body text
- **sm**: 0.875rem (14px) - Small text
- **xs**: 0.75rem (12px) - Captions

### Font Weights
- **medium**: 500 (Default for UI elements)
- **semibold**: 600 (Headings)
- **bold**: 700 (Strong emphasis)

---

## 🧱 Component Library

### Buttons
```typescript
// Usage: <Button variant="primary" size="default">
variants: 'primary' | 'secondary' | 'ghost' | 'destructive'
sizes: 'sm' | 'default' | 'lg'
```

**Button Classes:**
- `.cylvy-btn-primary` - Primary gradient with hover scale
- `.cylvy-btn-secondary` - Outline style with fill on hover
- `.cylvy-btn-ghost` - Transparent with subtle background

### Cards
```typescript
// Usage: <Card hover={true}>
props: hover, className
```

**Card System:**
- `.cylvy-card` - Base card with rounded corners and shadows
- `.cylvy-card-hover` - Interactive hover effects (scale + shadow)
- `.cylvy-card-header` - Header with bottom border
- `.cylvy-card-body` - Main content area
- `.cylvy-card-footer` - Footer with top border

### Form Elements
```css
.cylvy-input    /* Text inputs with focus states */
.cylvy-label    /* Form labels with proper spacing */
.cylvy-select   /* Dropdown selects with custom arrow */
```

### Tables
```css
.cylvy-table         /* Base table styling */
.cylvy-table-header  /* Header with borders */
.cylvy-table-row     /* Row hover effects */
.cylvy-table-cell    /* Cell padding and alignment */
```

---

## ✨ Animation System

### Keyframe Animations
```css
@keyframes cylvy-fade-in      /* 0.3s opacity transition */
@keyframes cylvy-slide-up     /* 0.4s slide and fade */
@keyframes cylvy-scale        /* 0.2s scale effect */
```

### Animation Classes
- `.animate-fade-in` - Gentle opacity entrance
- `.animate-slide-up` - Upward slide entrance  
- `.animate-scale` - Scale hover effect

### Timing Functions
```css
--ease-default: cubic-bezier(0.4, 0, 0.2, 1);
--duration-200: 200ms;
--duration-300: 300ms;
```

---

## 🎨 UI Patterns

### Background Gradients
- **Primary Gradient**: Amaranth to Grape (CTAs, highlights)
- **Dark Gradient**: Midnight to Slate (backgrounds)
- **Success Gradient**: Green tones for positive actions

### Interactive States
- **Hover**: Scale (105%) + enhanced shadows
- **Focus**: Ring outline in brand colors
- **Active**: Slightly scaled down (95%)
- **Disabled**: 50% opacity + pointer-events-none

### Shadows
```css
--shadow-cylvy-sm: 0 2px 4px rgba(229, 24, 72, 0.1)
--shadow-cylvy: 0 4px 6px rgba(229, 24, 72, 0.1), 0 1px 3px rgba(136, 6, 191, 0.08)
--shadow-cylvy-lg: 0 10px 15px rgba(229, 24, 72, 0.1), 0 4px 6px rgba(136, 6, 191, 0.08)
```

---

## 📱 Layout System

### Container Patterns
- **Dashboard Layout**: Sidebar + main content area
- **Card Grids**: Responsive grid layouts for data cards
- **Modal Dialogs**: Centered overlays with backdrop blur

### Navigation
- **Sidebar**: Collapsible navigation with icon + text
- **Top Bar**: Gradient background with user controls
- **Breadcrumbs**: Contextual navigation for deep pages

### Responsive Breakpoints
```css
sm: '640px'    /* Mobile landscape */
md: '768px'    /* Tablet */
lg: '1024px'   /* Desktop */
xl: '1280px'   /* Large desktop */
2xl: '1536px'  /* Extra large */
```

---

## 📊 Data Visualization

### Chart Colors
- **Chart 1**: `hsl(12, 76%, 61%)` - Primary data series
- **Chart 2**: `hsl(173, 58%, 39%)` - Secondary series
- **Chart 3**: `hsl(197, 37%, 24%)` - Tertiary series
- **Chart 4**: `hsl(43, 74%, 66%)` - Warning/attention
- **Chart 5**: `hsl(27, 87%, 67%)` - Accent series

### Data Table Styling
- **Header**: Dark background with uppercase labels
- **Rows**: Alternating with hover states
- **Cells**: Proper padding for data readability

---

## 🔧 Technical Implementation

### Framework Integration
- **CSS Framework**: Tailwind CSS 3.x
- **Component Library**: shadcn/ui components
- **Icons**: Lucide React
- **Build Tool**: Next.js with Tailwind

### CSS Architecture
```css
@layer base     /* Design tokens and CSS variables */
@layer components   /* Reusable component classes */
@layer utilities    /* Helper utilities */
```

### Design Token Structure
```css
:root {
  /* Brand tokens */
  --cylvy-[color-name]: [value];
  
  /* Semantic tokens */
  --color-[semantic]: [value];
  
  /* Component tokens */
  --[component]-[property]: [value];
}
```

---

## 📱 Component Examples

### Primary Button
```tsx
<Button variant="primary" size="default">
  Analyze Data
</Button>
```
**Output**: Gradient background, white text, hover scale, focus ring

### Interactive Card
```tsx
<Card hover={true}>
  <CardHeader>
    <CardTitle>Performance Metrics</CardTitle>
  </CardHeader>
  <CardContent>
    Data visualization content
  </CardContent>
</Card>
```

### Data Input
```tsx
<Label>Search Keywords</Label>
<Input className="cylvy-input" placeholder="Enter keyword..." />
```

---

## 🌙 Dark Mode Support

### Dark Theme Variables
```css
.dark {
  --background: var(--cylvy-midnight);
  --foreground: 243 244 246;
  --card: var(--cylvy-slate);
  --card-foreground: 229 231 235;
}
```

### Theme Toggle Support
- Automatic system preference detection
- Manual override capabilities
- Consistent contrast ratios across modes

---

## 🎯 Use Cases & Applications

### Ideal For:
- **Business Intelligence Dashboards**
- **Data Analytics Platforms**
- **Financial Services Applications**
- **Enterprise SaaS Tools**
- **Marketing Analytics Platforms**

### Key Strengths:
- **Professional Credibility**: Sophisticated color palette
- **Data Focus**: High contrast for extended reading
- **Brand Recognition**: Distinctive gradient system
- **Scalability**: Comprehensive component library
- **Accessibility**: WCAG compliant contrast ratios

---

## 📋 Implementation Guidelines

### Getting Started
1. **Install Dependencies**:
   ```bash
   npm install tailwindcss @tailwindcss/forms
   npm install tailwindcss-animate
   ```

2. **Configure Tailwind**:
   ```javascript
   // Copy Cylvy color extensions to tailwind.config.js
   ```

3. **Import Styles**:
   ```css
   @import 'cylvy-theme.css';
   ```

### Best Practices
- **Consistent Spacing**: Use the defined spacing scale
- **Gradient Usage**: Reserve gradients for primary actions
- **Interactive States**: Always include hover/focus states
- **Card Patterns**: Use cards for content grouping
- **Animation Restraint**: Subtle, purposeful motion only

---

## 🔮 Future Considerations

### Potential Extensions
- **Light Mode Optimization**: Enhanced light theme support
- **Mobile-First Components**: Touch-optimized interfaces
- **Data Visualization**: Expanded chart component library
- **Icon System**: Custom Cylvy icon set
- **Motion Language**: Extended animation system

### Component Roadmap
- Advanced data tables with sorting/filtering
- Dashboard widget library
- Chart component system
- Advanced form components
- Loading state patterns

---

**Created for**: Enterprise analytics applications  
**Based on**: nCino Digital Landscape Dashboard  
**Framework**: Next.js + Tailwind CSS  
**Last Updated**: September 2025

---

*This design system provides a solid foundation for building professional, data-centric applications with the distinctive Cylvy brand identity.*
