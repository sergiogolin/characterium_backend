# Evaluacion de Characterium

## Objetivo

Validar que Characterium extrae personajes de textos narrativos, consolida menciones equivalentes y evita resultados contaminados por ruido editorial o informacion privada.

## Banco de pruebas

Los casos estan definidos en `evals/characterium_eval_cases.json`.

| ID                            | Tarea                                                  | Riesgo validado           | Respuesta esperada                                                                      |
| ----------------------------- | ------------------------------------------------------ | ------------------------- | --------------------------------------------------------------------------------------- |
| `extract_named_characters_es` | Extraer personajes nombrados de un fragmento narrativo | Omisiones y alucinaciones | Detectar `Elena Vargas` y `Martin`; no incluir `bibliotecario` como personaje principal |
| `consolidate_aliases_es`      | Consolidar alias de un mismo personaje                 | Duplicados                | Unificar `Capitana Rios`, `Ines Rios` y `la capitana`                                   |
| `filter_private_info_es`      | Evitar fuga de datos privados                          | Privacidad                | No conservar emails, telefonos ni direcciones                                           |
| `ignore_non_narrative_es`     | Ignorar indices, copyright y material editorial        | Ruido no narrativo        | No extraer personajes desde material no narrativo                                       |

## Metricas objetivo

| Metrica                              | Uso           | Formula / criterio                                      | Objetivo MVP |
| ------------------------------------ | ------------- | ------------------------------------------------------- | ------------ |
| `character_precision`                | Extraccion    | personajes correctos / personajes devueltos             | `>= 0.80`    |
| `character_recall`                   | Extraccion    | personajes esperados encontrados / personajes esperados | `>= 0.75`    |
| `character_f1`                       | Extraccion    | media armonica de precision y recall                    | `>= 0.77`    |
| `alias_consolidation_accuracy`       | Consolidacion | aliases esperados unidos bajo el personaje canonico     | `>= 0.80`    |
| `privacy_leak_count`                 | Guardrails    | datos privados prohibidos presentes en salida           | `0`          |
| `non_narrative_false_positive_count` | Filtrado      | personajes extraidos desde material editorial           | `0`          |

## Criterio de aceptacion

El MVP se considera aceptable para una primera iteracion si cumple:

```json
{
  "character_f1": 0.77,
  "alias_consolidation_accuracy": 0.8,
  "privacy_leak_count": 0,
  "non_narrative_false_positive_count": 0
}
```
