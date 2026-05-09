Analiza este texto narrativo y extrae observaciones locales de personajes.

Devuelve SOLO JSON válido usando exactamente el esquema definido en el prompt de sistema.

Instrucciones adicionales:

- Incluye el `chunk_index` recibido en el campo top-level `"chunk_index"`.
- Antes de extraer, identifica qué líneas pertenecen al relato y cuáles son material externo al relato. Extrae SOLO de las líneas narrativas.
- Si el texto es material editorial, paratextual o externo al relato, devuelve el objeto JSON con este `chunk_index` y `"characters": []`.
- Ignora nombres propios de autores/as, cónyuges, familiares, editores/as, traductores/as, ilustradores/as, críticos/as, prologuistas o personas mencionadas en biografías, agradecimientos, reseñas, notas, créditos, prólogos editoriales, apéndices o secciones "sobre el autor".
- Si el chunk mezcla páginas preliminares/finales con relato, ignora solo el material externo y conserva la extracción de las escenas, diálogos y narración que sí pertenecen a la historia.
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
