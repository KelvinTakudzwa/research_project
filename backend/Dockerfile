FROM node:20-alpine

# Set working directory
WORKDIR /usr/src/app

# Copy package.json and install dependencies
COPY package*.json ./
RUN npm install

# Copy application source
COPY . .

# Expose backend port
EXPOSE 5000

# Start server
CMD ["node", "server.js"]
