# Build stage
FROM node:20-alpine as build-stage

# Set working directory
WORKDIR /app

# Copy package.json and install dependencies
COPY package*.json ./
RUN npm install

# Copy project files and build
COPY . .
RUN npm run build

# Production stage with Nginx
FROM nginx:stable-alpine as production-stage

# Copy built files from build stage to nginx serve directory
COPY --from=build-stage /app/dist /usr/share/nginx/html

# Copy custom nginx configuration if needed
# COPY nginx.conf /etc/nginx/conf.d/default.conf

# Expose port 80
EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]