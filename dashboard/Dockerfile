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

# Install serve to run the application
RUN npm install -g serve

# Copy only the built assets from the builder stage
COPY --from=builder /app/dist ./dist

# Expose port 3000
EXPOSE 3000

# Start the app with SPA routing fallback (-s)
CMD ["serve", "-s", "dist", "-l", "3000"]
