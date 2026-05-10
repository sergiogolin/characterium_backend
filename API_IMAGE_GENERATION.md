# API de Generación de Imágenes

Este documento describe el nuevo endpoint para generar imágenes de personajes.

## Endpoints

### 1. POST /api/generate-image

Inicia la generación asíncrona de una imagen de personaje.

**Request:**

```json
{
  "prompt": "Descripción del personaje o escena",
  "style": "fotorrealista" // opcional, default: "fotorrealista"
}
```

**Response (202 Accepted):**

```json
{
  "jobId": "uuid-string",
  "message": "Generación de imagen iniciada"
}
```

**Ejemplo con curl:**

```bash
curl -X POST http://localhost:8000/api/generate-image \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Un joven noble con cabello oscuro y ojos azules, vistiendo ropa medieval elegante",
    "style": "fotorrealista"
  }'
```

**Ejemplo con JavaScript (fetch):**

```javascript
const response = await fetch("http://localhost:8000/api/generate-image", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({
    prompt:
      "Un joven noble con cabello oscuro y ojos azules, vistiendo ropa medieval elegante",
    style: "fotorrealista",
  }),
});
const data = await response.json();
const jobId = data.jobId;
```

---

### 2. GET /api/generate-image/{job_id}

Consulta el estado de una generación de imagen.

**Response si está en proceso:**

```json
{
  "status": "processing",
  "message": "Generando imagen..."
}
```

**Response si completó exitosamente:**

```json
{
  "status": "completed",
  "imagePath": "/images/generated/abc123def456.png",
  "imageUrl": "http://localhost:8000/images/generated/abc123def456.png"
}
```

**Response si falló:**

```json
{
  "status": "failed",
  "error": "Descripción del error ocurrido"
}
```

**Ejemplo con curl:**

```bash
curl http://localhost:8000/api/generate-image/uuid-string
```

**Ejemplo con JavaScript (fetch):**

```javascript
const jobId = "uuid-string";
const response = await fetch(
  `http://localhost:8000/api/generate-image/${jobId}`,
);
const status = await response.json();

if (status.status === "completed") {
  console.log("Imagen lista:", status.imageUrl);
} else if (status.status === "processing") {
  console.log("Aún procesando...");
} else if (status.status === "failed") {
  console.error("Error:", status.error);
}
```

---

## Flujo de Uso Recomendado

1. **Hacer request POST** a `/api/generate-image` con prompt y estilo
2. **Guardar el jobId** de la respuesta
3. **Hacer polling** a `/api/generate-image/{jobId}` hasta que tenga resultado
4. **Usar la imagen** cuando el status sea "completed"

### Ejemplo completo con polling:

```javascript
async function generateCharacterImage(prompt, style = "fotorrealista") {
  // 1. Iniciar generación
  const initResponse = await fetch("http://localhost:8000/api/generate-image", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ prompt, style }),
  });

  const { jobId } = await initResponse.json();

  // 2. Hacer polling cada 2 segundos
  return new Promise((resolve, reject) => {
    const checkStatus = async () => {
      const statusResponse = await fetch(
        `http://localhost:8000/api/generate-image/${jobId}`,
      );
      const status = await statusResponse.json();

      if (status.status === "completed") {
        resolve(status);
      } else if (status.status === "failed") {
        reject(new Error(status.error));
      } else {
        // Sigue esperando
        setTimeout(checkStatus, 2000);
      }
    };

    checkStatus();
  });
}

// Uso
try {
  const result = await generateCharacterImage(
    "Un guerrero con cicatrices, armadura desgastada y mirada guerrera",
    "realista oscuro",
  );
  console.log("Imagen lista:", result.imageUrl);
} catch (error) {
  console.error("Error:", error.message);
}
```

---

## Configuración

La generación de imágenes usa un LLM configurado con el prefijo `IMAGE_GENERATION` en `config/app_config.json`:

```json
{
  "IMAGE_GENERATION_LLM_MODE": "ollama",
  "IMAGE_GENERATION_LLM_MODEL_ID": "qwen2.5:7b",
  "IMAGE_GENERATION_LLM_TEMPERATURE": 0.7
}
```

### Parámetros configurables:

- **IMAGE_GENERATION_LLM_MODE**: Provider del LLM (ollama, openrouter, gemini, hugging_face)
- **IMAGE_GENERATION_LLM_MODEL_ID**: ID/nombre del modelo
- **IMAGE_GENERATION_LLM_TEMPERATURE**: Temperatura para el LLM (0.0-1.0)

---

## Arquitectura

### Flujo de procesamiento:

1. **Request llega** → Se crea un `job_id` único
2. **Background task** inicia:
   - Genera prompt optimizado para imagen usando el LLM
   - Llama al modelo de generación de imágenes
   - Guarda imagen con nombre hash aleatorio
   - Actualiza estado en memoria
3. **Frontend hace polling** → Obtiene estado y URL de imagen cuando esté lista

### Almacenamiento:

- **Carpeta**: `./public/images/generated/`
- **Nombres**: Hash SHA256 de 12 caracteres + extensión
- **URL pública**: `http://localhost:8000/images/generated/{hash}.{ext}`

### Generación de prompts:

El sistema usa prompts en:

- `app/core/prompts/image_generation/system.md`
- `app/core/prompts/image_generation/user.md`

El LLM procesa la descripción del personaje + estilo gráfico y genera un prompt optimizado para modelos de difusión.

---

## Estilos gráficos soportados

Ejemplos de estilos que puedes usar:

- `fotorrealista` (default)
- `anime`
- `estilo comic`
- `acuarela`
- `óleo clásico`
- `3D CGI`
- `ilustración digital`
- `realismo oscuro`
- Cualquier otro estilo descriptivo

---

## Limitaciones actuales

⚠️ **IMPORTANTE**: La generación de imágenes requiere un modelo LLM que soporte generación de imágenes:

- **Ollama**: Necesita modelos como `flux.1`, `stable-diffusion-xl`, etc.
- **OpenRouter**: Muchos modelos soportan imagen
- **Gemini**: API de generación de imágenes
- **HuggingFace**: Modelos de difusión

Si usas un modelo que no genera imágenes, el endpoint retornará error informando que se necesita un modelo compatible.

---

## Troubleshooting

### "Error generando imagen: Model not found"

- Verifica que el modelo LLM en config existe y tiene soporte para imagen

### "Job no encontrado"

- El job_id expiró (no está implementada limpieza de estado antiguo aún)

### Imágenes vacías o errores

- Verifica los logs del backend (`DEBUG_PIPELINE: true` en config)
- Asegúrate de que el LLM tiene suficientes recursos

---

## Mejoras futuras

- [ ] Limpieza automática de imágenes antiguas
- [ ] Soporte para webhooks en lugar de polling
- [ ] Persistencia de estado en base de datos
- [ ] Caché de imágenes generadas
- [ ] Verificación de marca de agua
- [ ] Listar imágenes generadas
- [ ] Endpoint para eliminar imágenes
