# ---------- Build stage ----------
FROM node:24.11.1-alpine AS builder

WORKDIR /app

# Install dependencies
COPY package*.json ./
RUN npm ci

# Copy source code
COPY . .

# Create production build
RUN npm run build


# ---------- Production stage ----------
FROM nginxinc/nginx-unprivileged:alpine

# Remove default nginx files
# Using user root to clear the folder if necessary, though unprivileged image already sets up proper dirs
USER root
RUN rm -rf /usr/share/nginx/html/*
USER nginx

# Copy Vite production build
COPY --from=builder /app/dist /usr/share/nginx/html

# Copy the nginx template
COPY default.conf.template /etc/nginx/templates/default.conf.template

# Expose HTTP
EXPOSE 8080

# Start nginx
CMD ["nginx", "-g", "daemon off;"]