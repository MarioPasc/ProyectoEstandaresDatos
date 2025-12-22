# SPARQL Runner (RDFlib) — Uso

Este documento describe el comportamiento del script `run_sparql.py`: qué hace, cómo procesa las consultas, qué formatos genera y qué incluye el índice de ejecución.

---

## 1) Propósito

El runner ejecuta un **pack de consultas SPARQL (`*.rq`)** sobre un **grafo RDF** (fichero Turtle, normalmente `export.ttl`) usando **RDFlib**.

Funciones principales:

1. **Carga** un grafo RDF desde un fichero `.ttl`
2. **Descubre** automáticamente ficheros de consulta `*.rq` en un directorio
3. **Ejecuta** cada consulta contra el grafo
4. **Exporta resultados** por consulta (CSV/JSON o TTL según el tipo)
5. **Genera un índice/resumen** con métricas (tiempo, filas, columnas, outputs, errores)

---

## 2) Flujo de ejecución (paso a paso)

### 2.1 Carga del grafo
- Lee el fichero Turtle de entrada.
- Parseo con RDFlib (`Graph().parse(..., format="turtle")`).
- Si el TTL no existe o no se puede parsear, el script finaliza con error.

Además, extrae:
- **Número total de triples** del grafo (para el manifiesto de ejecución).
- **Prefijos** disponibles en el `namespace_manager` del grafo.

### 2.2 Descubrimiento de consultas
- Busca ficheros `*.rq` en el directorio indicado.
- Puede ser:
  - **no recursivo**: solo `dir/*.rq`
  - **recursivo**: `dir/**/*.rq`

Las consultas se ordenan de forma determinista (orden alfabético por ruta).

### 2.3 Preparación de prefijos (compatibilidad)
Para maximizar la compatibilidad:

- Si una consulta ya declara `PREFIX`, se respetan.
- Si faltan prefijos, el runner puede **inyectar prefijos disponibles** desde:
  1) Prefijos del grafo (namespace manager)  
  2) Un fichero opcional externo de prefijos (si se proporciona)

El resultado es una consulta final “enriquecida” con los `PREFIX` que falten, evitando duplicados.

### 2.4 Ejecución de consultas
Para cada `.rq`:

- Se mide el tiempo (ms) con un temporizador de alta resolución.
- Se ejecuta `graph.query(query_text)`.
- Se detecta el **tipo de consulta** (best-effort):
  - `SELECT`, `ASK`, `CONSTRUCT`, `DESCRIBE` (o `UNKNOWN` si no puede inferirse)

En caso de fallo:
- Se marca la consulta como `ok=false`
- Se guarda el mensaje de error en el índice
- Si está activado `--fail-fast`, se aborta el resto del pack.

---

## 3) Exportación de resultados por tipo de consulta

Cada consulta genera una subcarpeta con el nombre *slugificado* del `.rq` (p.ej. `my_query.rq` → `my_query/`).

### 3.1 SELECT
Convierte el resultado tabular (bindings) a:

- **JSON**
  - `result.json`
  - Estructura:
    - `columns`: lista de variables
    - `rows`: lista de objetos `{var: value_string}`
- **CSV**
  - `result.csv`
  - Cabecera con las variables
  - Una fila por binding

Notas:
- Los valores se serializan preferentemente en formato compacto usando prefijos (`n3(namespace_manager)`) cuando es posible.
- Si un valor es `NULL`/ausente, se exporta como cadena vacía.

### 3.2 ASK
Genera:

- **JSON**
  - `result.json`
  - Estructura:
    - `type`: `"ASK"`
    - `query`: nombre del fichero `.rq`
    - `boolean`: `true/false`

### 3.3 CONSTRUCT / DESCRIBE
Materializa un grafo resultado y genera:

- **TTL**
  - `result.ttl`
  - Serialización Turtle del grafo resultante

Opcional:
- Si el runner tiene activado JSON en formatos, genera además:
  - `summary.json` con un resumen mínimo
    - `type`: `"CONSTRUCT"` o `"DESCRIBE"`
    - `triples`: número de triples del grafo de salida

Métrica reportada:
- `rows`: número de triples del grafo de salida
- `cols`: 3 (sujeto, predicado, objeto)

### 3.4 Tipos no detectados (UNKNOWN)
Si no puede determinar el tipo, intenta tratarlas como resultado tabular exportable a JSON.

---

## 4) Índice / manifiesto de ejecución

El runner genera dos ficheros de índice:

### 4.1 `index.json`
Incluye metadata y un listado de reportes por consulta, por ejemplo:

- timestamp UTC
- ruta del TTL de entrada
- ruta del directorio de consultas
- ruta de salida
- versión de Python, plataforma, versión de RDFlib
- número total de triples del grafo de entrada
- lista de queries con:
  - `query_file`, `query_name`, `query_type`
  - `ok`
  - `duration_ms`
  - `rows`, `cols`
  - `outputs` (rutas de ficheros generados)
  - `error` (si falla)

### 4.2 `index.md`
Resumen humano legible con una tabla:

| query | type | ok | ms | rows | cols | outputs |
|------|------|----|----|------|------|---------|

---

## 5) Códigos de salida

- `0`: todas las consultas ejecutadas correctamente
- `1`: alguna consulta falló (pero el script terminó generando índice)
- `2`: error de runner/configuración (TTL no existe, no hay consultas, parseo TTL falla, etc.)

---

## 6) Parámetros CLI (comportamiento)

> Los nombres exactos pueden variar según vuestra implementación final, pero el runner típico incluye:

- `--ttl`: ruta al fichero Turtle de entrada
- `--queries`: directorio con `.rq`
- `--out`: directorio de salida de resultados
- `--recursive`: búsqueda recursiva de `.rq`
- `--format`: `csv` y/o `json` (repetible)
- `--prefixes`: fichero opcional con líneas `PREFIX`
- `--fail-fast`: aborta al primer fallo
- `--dry-run`: no escribe ficheros (pero ejecuta y mide)
- `--verbose`: más logging

---

## 7) Estructura de salida

Salida típica:

<out>/
index.json
index.md
<query_slug_1>/
result.csv
result.json
<query_slug_2>/
result.json
<query_slug_3>/
result.ttl
summary.json

---

## 8) Limitaciones conocidas

- La detección de tipo de query es “best-effort” (heurística); si el fichero tiene comentarios/estructura rara, puede caer en `UNKNOWN`.
- En `CONSTRUCT/DESCRIBE`, el runner exporta TTL; el JSON asociado (si se genera) es solo resumen (no vuelca todo el RDF a JSON).
- La serialización de términos prioriza `n3()` (prefijos); si el grafo no tiene bindings de prefijos, se mostrará como IRI completa.

---

## 9) Ejemplo de ejecución

Ejecutar pack con export a CSV+JSON y resumen:

```bash
python tools/run_sparql.py --format csv --format json --verbose
```