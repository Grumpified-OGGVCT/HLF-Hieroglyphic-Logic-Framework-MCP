FROM node:20-alpine

WORKDIR /app

# Install dependencies first for layer caching
COPY package.json ./
RUN npm install --production=false

# Copy source
COPY . .

# Create upload directory
RUN mkdir -p uploads

EXPOSE 3000

CMD ["npm", "start"]
