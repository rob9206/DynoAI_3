# DynoAI Frontend Dockerfile
# Multi-stage build for optimized production image

# =============================================================================
# Stage 1: Dependencies
# =============================================================================
FROM node:20-alpine as deps

WORKDIR /app

# Copy package files
COPY package.json package-lock.json ./

# Install dependencies
RUN npm ci --legacy-peer-deps

# =============================================================================
# Stage 2: Build
# =============================================================================
FROM node:20-alpine as builder

WORKDIR /app

# Copy dependencies from deps stage
COPY --from=deps /app/node_modules ./node_modules

# Copy source code
COPY . .

# Build arguments for environment configuration
ARG VITE_API_URL=http://localhost:5001
ENV VITE_API_URL=$VITE_API_URL

# Build the application
RUN npm run build

# =============================================================================
# Stage 3: Production with Nginx
# =============================================================================
FROM nginx:alpine as production

ARG DYNOAI_VERSION=0.0.0-dev

# Labels
LABEL org.opencontainers.image.title="DynoAI Frontend"
LABEL org.opencontainers.image.description="DynoAI Web Dashboard"
LABEL org.opencontainers.image.version="${DYNOAI_VERSION}"

# Remove default nginx config
RUN rm /etc/nginx/conf.d/default.conf

# Copy custom nginx configuration
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Copy built assets from builder
COPY --from=builder /app/dist /usr/share/nginx/html

# Create non-root user
RUN addgroup -g 1000 dynoai && \
    adduser -u 1000 -G dynoai -s /bin/sh -D dynoai && \
    chown -R dynoai:dynoai /usr/share/nginx/html && \
    chown -R dynoai:dynoai /var/cache/nginx && \
    chown -R dynoai:dynoai /var/log/nginx && \
    touch /var/run/nginx.pid && \
    chown -R dynoai:dynoai /var/run/nginx.pid

# Expose port
EXPOSE 80

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD wget -q --spider http://localhost:80 || exit 1

# Run nginx
CMD ["nginx", "-g", "daemon off;"]

# =============================================================================
# Stage 4: Development
# =============================================================================
FROM node:20-alpine as development

WORKDIR /app

# Copy package files
COPY package.json package-lock.json ./

# Install all dependencies including devDependencies
RUN npm ci --legacy-peer-deps

# Copy source code
COPY . .

# Expose Vite dev server port
EXPOSE 5173

# Development command
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]

