# frontend/Dockerfile

FROM node:18-alpine AS builder

WORKDIR /app

# Copy package files
COPY package*.json ./

# Copy .env.local so that Next.js can load it at build time
COPY .env.local .env.local

RUN npm install

# Copy the rest of your code
COPY . .

RUN npm run build

FROM node:18-alpine
WORKDIR /app

COPY --from=builder /app/.next ./.next
COPY --from=builder /app/package*.json ./
COPY --from=builder /app/node_modules ./node_modules

# Also copy .env.local if you need runtime access
COPY .env.local .env.local

EXPOSE 3000

CMD ["npm", "run", "start"]