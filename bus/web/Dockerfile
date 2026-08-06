# Avtobus web (Nuxt) — poyezd.uz'dan moslashtirilgan. Build + yengil runtime.
FROM node:20-slim AS build
WORKDIR /app
COPY package.json package-lock.json ./
# npm ci qat'iy (lock+package.json aniq mos bo'lishi shart). Konteynerdagi npm
# versiyasi lock'ni rad etsa — npm install'ga tushamiz (deploy to'xtab qolmasin).
RUN npm ci || npm install
COPY . .
RUN npm run build

FROM node:20-slim
WORKDIR /app
ENV NODE_ENV=production \
    NITRO_PORT=3000 \
    NITRO_HOST=0.0.0.0
COPY --from=build /app/.output ./.output
EXPOSE 3000
CMD ["node", ".output/server/index.mjs"]
