FROM node:22-alpine

WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm install

# El código se monta como volumen en docker-compose.yml; node_modules vive en
# un volumen propio para no pisarse con la carpeta del host.
COPY . .

EXPOSE 5173

# npm install al arrancar: el volumen de node_modules conserva su contenido
# entre reconstrucciones, así que se sincroniza con package.json en cada inicio
# (si no hay cambios termina en un par de segundos).
CMD ["sh", "-c", "npm install --no-audit --no-fund && npm run dev"]
