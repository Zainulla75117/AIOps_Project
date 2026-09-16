# Build Stage
FROM node:24.11.1-alpine AS builder

WORKDIR /app

# Install dependencies
COPY package.json package-lock.json ./
RUN npm ci

# Copy source and build
COPY . .
RUN npm run build

# Production Stage
FROM node:24.11.1-alpine

WORKDIR /app

# Copy necessary files from the builder stage
COPY --from=builder /app/package.json ./
COPY --from=builder /app/vite.config.ts ./
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/dist ./dist

# Vite preview runs on 4173
EXPOSE 4173

# Start the app using Vite's preview server which maintains the proxy logic
CMD ["npm", "run", "preview"]
