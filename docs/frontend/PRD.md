# Planning Guide

A two-page dyno tuning analysis application that processes CSV data files to analyze engine performance and visualizes volumetric efficiency in 3D space.

**Experience Qualities**: 
1. **Professional** - Clean, technical interface that inspires confidence in data accuracy
2. **Efficient** - Streamlined workflow from upload to visualization with clear progress indicators
3. **Insightful** - Rich data presentation that makes complex tuning metrics immediately understandable

**Complexity Level**: Light Application (multiple features with basic state)
  - Two distinct pages with file processing, data analysis simulation, and 3D visualization capabilities

## Essential Features

### CSV File Upload & Analysis
- **Functionality**: Accept CSV file upload, parse contents, simulate analysis pipeline
- **Purpose**: Initiate the dyno data analysis workflow
- **Trigger**: User selects CSV file and clicks "Analyze"
- **Progression**: File selection → Upload → Parsing → Analysis simulation → Status updates → Results display
- **Success criteria**: File successfully parsed, manifest stats generated, downloadable results available

### Manifest Statistics Display
- **Functionality**: Show key metrics from analysis (rows processed, corrections applied, output files)
- **Purpose**: Provide immediate feedback on analysis results
- **Trigger**: Analysis completion
- **Progression**: Analysis completes → Parse manifest → Display stats grid → Show file links
- **Success criteria**: Clear presentation of all manifest data with working download links

### 3D VE Surface Visualization
- **Functionality**: Generate and render before/after 3D volumetric efficiency surfaces
- **Purpose**: Visual comparison of tuning improvements
- **Trigger**: User navigates to Visualize page after analysis
- **Progression**: Page load → Generate 3D meshes → Render interactive surfaces → Enable rotation/zoom
- **Success criteria**: Smooth 3D visualization with clear before/after comparison

### Page Navigation
- **Functionality**: Tab-based navigation between Analyze and Visualize pages
- **Purpose**: Organize workflow into logical steps
- **Trigger**: User clicks tab
- **Progression**: Tab click → Content switch → State preservation
- **Success criteria**: Smooth transitions, state persists across navigation

## Edge Case Handling
- **No file selected**: Disable analyze button until file is chosen
- **Invalid CSV format**: Display clear error message with format requirements
- **Large files**: Show processing indicator to manage user expectations
- **No analysis run**: Visualize page shows prompt to run analysis first
- **Browser compatibility**: Graceful fallback if WebGL unavailable for 3D

## Design Direction

The design should feel professional and technical - like software an automotive engineer would trust for critical tuning work. Clean data tables, precise typography, and purposeful use of color to highlight important metrics. The interface should be minimal and focused, letting the data and visualizations take center stage.

## Color Selection

Triadic color scheme - using automotive-inspired colors that evoke precision engineering: deep blue for professionalism, vibrant orange for data highlights, and neutral grays for structure.

- **Primary Color**: Deep blue (oklch(0.35 0.08 250)) - Professional, technical, trustworthy
- **Secondary Colors**: Slate gray (oklch(0.45 0.02 250)) - Neutral backgrounds and secondary elements
- **Accent Color**: Performance orange (oklch(0.65 0.15 45)) - Highlighting key metrics and CTAs
- **Foreground/Background Pairings**:
  - Background (Light gray oklch(0.98 0.005 250)): Dark text oklch(0.2 0.01 250) - Ratio 12.8:1 ✓
  - Card (White oklch(1 0 0)): Dark text oklch(0.2 0.01 250) - Ratio 14.1:1 ✓
  - Primary (Deep blue oklch(0.35 0.08 250)): White text oklch(1 0 0) - Ratio 8.2:1 ✓
  - Secondary (Slate oklch(0.45 0.02 250)): White text oklch(1 0 0) - Ratio 5.8:1 ✓
  - Accent (Orange oklch(0.65 0.15 45)): Dark text oklch(0.2 0.01 250) - Ratio 5.1:1 ✓
  - Muted (Light slate oklch(0.95 0.01 250)): Mid gray text oklch(0.5 0.02 250) - Ratio 5.2:1 ✓

## Font Selection

Typefaces should convey precision and technical expertise - using a modern monospace for data/numbers and a clean sans-serif for UI elements.

- **Typographic Hierarchy**: 
  - H1 (Page Title): Inter Bold/32px/tight letter spacing
  - H2 (Section Headers): Inter SemiBold/20px/normal spacing
  - H3 (Stat Labels): Inter Medium/14px/wide letter spacing (uppercase)
  - Body (Descriptions): Inter Regular/16px/relaxed line height
  - Data/Numbers: JetBrains Mono Medium/16px/tabular figures
  - Captions: Inter Regular/14px/muted color

## Animations

Animations should be subtle and functional - reinforcing the professional tone while providing smooth feedback for interactions. Movement should feel precise and mechanical, like well-engineered machinery.

- **Purposeful Meaning**: Quick, precise transitions that mirror the technical nature of the application
- **Hierarchy of Movement**: 
  - Primary: File upload interaction and analysis progress (300ms ease)
  - Secondary: Tab transitions and stat reveals (200ms ease-out)
  - Tertiary: 3D surface rotation (smooth, physics-based)

## Component Selection

- **Components**: 
  - Tabs (shadcn) - Navigation between Analyze and Visualize pages
  - Card (shadcn) - Container for stats and file upload area
  - Button (shadcn) - Primary actions with icon support
  - Progress (shadcn) - Analysis status indicator
  - Alert (shadcn) - Error messages and warnings
  - Badge (shadcn) - File type indicators and status labels
  - Input (shadcn) - File input styling
  - Separator (shadcn) - Visual section breaks
  
- **Customizations**: 
  - Custom 3D canvas component using Three.js for VE surface rendering
  - Custom file upload dropzone with drag-and-drop
  - Custom stats grid with monospace numbers
  
- **States**: 
  - Buttons: Default (solid primary), hover (slight lift + shadow), active (pressed), disabled (muted with reduced opacity)
  - File input: Empty (dashed border), has file (solid border with green accent), error (red accent)
  - Tabs: Inactive (muted), active (primary with bottom border), hover (slight background)
  
- **Icon Selection**: 
  - FileArrowUp (upload action)
  - Play (analyze action)
  - ChartLine (analysis indicator)
  - Cube (3D visualization)
  - DownloadSimple (file downloads)
  - CheckCircle (success states)
  
- **Spacing**: 
  - Page padding: p-6 (24px)
  - Card padding: p-6
  - Section gaps: gap-6
  - Stat grid: gap-4
  - Button spacing: px-6 py-2
  
- **Mobile**: 
  - Stack stats grid vertically on mobile (<768px)
  - Full-width buttons on mobile
  - Reduce page padding to p-4
  - Tab labels may abbreviate ("Analyze" → "Run", "Visualize" → "VE")
  - 3D canvas scales proportionally with touch controls
