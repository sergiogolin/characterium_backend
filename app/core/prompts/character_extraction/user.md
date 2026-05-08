Analiza este texto narrativo y extrae observaciones locales de personajes.

Devuelve SOLO JSON válido usando exactamente el esquema definido en el prompt de sistema.

Instrucciones adicionales:

- Incluye el `chunk_index` recibido en el campo top-level `"chunk_index"`.
- Si el texto es material editorial o externo al relato, devuelve el objeto JSON con este `chunk_index` y `"characters": []`.
- Si no hay personajes útiles en el texto, devuelve el objeto JSON con este `chunk_index` y `"characters": []`.
- Usa citas breves, no párrafos enteros.
- No repitas informacion en varios campos si no aporta valor.
- Si una motivación no es evidente, déjala vacía u omite el campo según el esquema.
- Si una relación no aparece claramente identificada, no la inventes.

chunk_index: {{CHUNK_INDEX}}

chunk_text:
"""
{{CHUNK_TEXT}}
"""
