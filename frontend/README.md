# Soul Squad - Frontend

A modern, responsive wellbeing platform built with Next.js, React, and Tailwind CSS.

## 🚀 Getting Started

### Prerequisites

- Node.js 18+ and npm/yarn
- Git

### Installation

```bash
# Navigate to frontend directory
cd frontend

# Install dependencies
npm install

# Run development server
npm run dev

# Open browser
# Navigate to http://localhost:3000
```

### Build for Production

```bash
npm run build
npm start
```

## 📁 Project Structure

```
frontend/
├── src/
│   ├── app/                      # Next.js App Router
│   │   ├── layout.tsx           # Root layout
│   │   ├── page.tsx             # Marketing home page (/)
│   │   ├── globals.css          # Global styles & Tailwind
│   │   ├── app/                 # User dashboard routes
│   │   │   └── page.tsx         # User dashboard (/app)
│   │   └── consultant/          # Consultant dashboard routes
│   │       └── page.tsx         # Consultant dashboard (/consultant)
│   │
│   └── components/              # Reusable React components
│       ├── Header.tsx           # Site header with navigation
│       ├── Footer.tsx           # Site footer
│       └── ProtectedLayout.tsx  # Authenticated area layout
│
├── public/                      # Static assets
├── package.json                 # Dependencies
├── tsconfig.json               # TypeScript config
├── tailwind.config.js          # Tailwind CSS config
├── postcss.config.js           # PostCSS config
└── next.config.js              # Next.js config
```

## 🎨 Design System

### Colors

- **Primary**: Blue gradient (for main actions, links)
- **Secondary**: Purple gradient (for accents, highlights)
- **Accent**: Yellow (for tips, notifications)
- **Semantic**: Green (success), Red (errors), Gray (neutral)

### Typography

- **Display Font**: Outfit (headings, titles)
- **Body Font**: Inter (paragraphs, UI text)

### Components

All components use Tailwind utility classes with custom component classes defined in `globals.css`:

- `.btn` - Base button styles
- `.btn-primary` - Primary gradient button
- `.btn-secondary` - Outlined button
- `.btn-accent` - Accent gradient button
- `.card` - Card container
- `.card-hover` - Card with hover effect
- `.gradient-text` - Gradient text effect
- `.glass` - Glassmorphism effect

## 📄 Pages Overview

### Marketing Pages

#### `/` - Home Page
- **Hero Section**: Welcome message, CTA buttons, trust indicators
- **Why Us Section**: Key features, age group approaches
- **Services Section**: Service cards with pricing
- **Testimonials Section**: Client reviews
- **CTA Section**: Final call-to-action

### Authenticated Pages

#### `/app` - User Dashboard
- Quick stats (heart rate, journal entries, sessions)
- Mood tracker
- Quick actions (scan vitals, write journal, AI chat, book session)
- Recent journal entries
- Upcoming sessions
- Wellness score
- Daily tips

#### `/consultant` - Consultant Dashboard
- Stats (active clients, sessions, earnings, rating)
- Today's schedule with client sessions
- Recent client activity
- Pending messages
- Performance metrics
- Quick actions

## 🔐 Authentication (Placeholder)

Currently, authentication is implemented as placeholders:

- Login/Signup buttons in header (no functionality yet)
- Protected routes use `ProtectedLayout` component
- User data is mocked in dashboards

**To implement real auth:**
1. Add authentication provider (NextAuth.js, Clerk, etc.)
2. Update `ProtectedLayout` to check auth status
3. Add redirect logic for unauthenticated users
4. Connect login/signup buttons to auth flow

## 🎯 Key Features

### Responsive Design
- Mobile-first approach
- Breakpoints: sm (640px), md (768px), lg (1024px), xl (1280px)
- Mobile menu for navigation
- Collapsible sidebar on mobile dashboards

### Animations
- Fade-in effects on page load
- Slide-up animations for hero content
- Hover transitions on cards and buttons
- Smooth page transitions

### Accessibility
- Semantic HTML elements
- ARIA labels (to be expanded)
- Keyboard navigation support
- Color contrast compliance

## 🛠️ Development Guidelines

### Adding New Pages

1. Create page file in appropriate directory under `src/app/`
2. Use existing components (Header, Footer, ProtectedLayout)
3. Follow Tailwind utility-first approach
4. Add route to navigation in Header or ProtectedLayout

### Creating Components

1. Create `.tsx` file in `src/components/`
2. Use TypeScript for type safety
3. Add JSDoc comments for documentation
4. Export as default or named export

### Styling

1. Use Tailwind utility classes first
2. Create custom classes in `globals.css` for repeated patterns
3. Use `@layer components` for component-specific styles
4. Maintain consistent spacing (4px base unit)

## 📦 Dependencies

### Core
- `next` - React framework
- `react` & `react-dom` - UI library
- `typescript` - Type safety

### Styling
- `tailwindcss` - Utility-first CSS
- `postcss` & `autoprefixer` - CSS processing

### Icons
- `lucide-react` - Modern icon library

## 🚧 TODO / Future Enhancements

- [ ] Implement real authentication
- [ ] Connect to backend API
- [ ] Add form validation
- [ ] Implement data fetching with React Query
- [ ] Add loading states and skeletons
- [ ] Implement error boundaries
- [ ] Add unit tests (Jest + React Testing Library)
- [ ] Add E2E tests (Playwright)
- [ ] Optimize images with Next.js Image component
- [ ] Add SEO meta tags for all pages
- [ ] Implement dark mode toggle
- [ ] Add internationalization (i18n)

## 📝 Notes for Developers

### Tailwind Custom Classes

The project uses custom Tailwind classes defined in `globals.css`. Key classes:

- **Buttons**: `btn`, `btn-primary`, `btn-secondary`, `btn-accent`
- **Cards**: `card`, `card-hover`
- **Layout**: `section`, `container-custom`
- **Effects**: `gradient-text`, `glass`

### Component Patterns

1. **Client Components**: Use `'use client'` directive for interactive components
2. **Server Components**: Default in Next.js 14 App Router
3. **Layouts**: Wrap pages with shared UI (Header, Footer, Sidebar)
4. **Composition**: Build complex UIs from smaller components

### File Naming

- Components: PascalCase (e.g., `Header.tsx`)
- Pages: lowercase (e.g., `page.tsx`)
- Utilities: camelCase (e.g., `apiClient.ts`)

## 🤝 Contributing

1. Follow existing code style
2. Add comments for complex logic
3. Test responsive design on multiple devices
4. Ensure accessibility standards
5. Update this README for significant changes

## 📄 License

Proprietary - Soul Squad Platform

---

**Built with ❤️ using Next.js, React, and Tailwind CSS**
