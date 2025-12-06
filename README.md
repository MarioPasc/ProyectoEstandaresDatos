```
════════════════════════════════════════════════════════════════════════════════════════════
                                                                                            
██████╗ ██╗ ██████╗ ██╗███╗   ██╗████████╗███████╗ ██████╗ ██████╗  █████╗ ████████╗███████╗
██╔══██╗██║██╔═══██╗██║████╗  ██║╚══██╔══╝██╔════╝██╔════╝ ██╔══██╗██╔══██╗╚══██╔══╝██╔════╝
██████╔╝██║██║   ██║██║██╔██╗ ██║   ██║   █████╗  ██║  ███╗██████╔╝███████║   ██║   █████╗  
██╔══██╗██║██║   ██║██║██║╚██╗██║   ██║   ██╔══╝  ██║   ██║██╔══██╗██╔══██║   ██║   ██╔══╝  
██████╔╝██║╚██████╔╝██║██║ ╚████║   ██║   ███████╗╚██████╔╝██║  ██║██║  ██║   ██║   ███████╗ 
╚═════╝ ╚═╝ ╚═════╝ ╚═╝╚═╝  ╚═══╝   ╚═╝   ╚══════╝ ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝   ╚═╝   ╚══════╝
                                                                                            
                                                                                            
                      Pipeline de Integración de Datos Bioinformáticos                      
                         GDC · HGNC · UniProt → MongoDB / JSON                              
                                                                                            
════════════════════════════════════════════════════════════════════════════════════════════
```
- **DATOS GENERALES**
  - Proyecto:       BioIntegrate - Pipeline de Integración de Datos Bioinformáticos
  - Versión:        0.1.0
  - Asignatura:     Estándares de Datos
  - Universidad:    Universidad de Málaga (UMA)
  - Curso académico: 2024-2025
  - Repositorio:    https://github.com/MarioPasc/ProyectoEstandaresDatos

- **TUTOR ASIGNADO**
  - Nombre:         Dr.Rybinski, Maciej
  - Universidad:    Universidad de Málaga (UMA)

- **EQUIPO DE DESARROLLO**
  1. Mario Pascual-González
     Email: mpascual@uma.es
     Rol:   Developer

  2. Teresa Vega Martínez
     Email: teresavegamar@gmail.com
     Rol:   Developer

  3. Juan Soriano
     Email: 0610948742@uma.es
     Rol:   Developer

  4. Ainhoa Pérez
     Email: ainhoa140602@gmail.com
     Rol:   Developer

  5. Martina Cebolla Salas
     Email: martinacesalas@gmail.com
     Rol:   Developer

<!-- TOC start (generated with https://github.com/derlin/bitdowntoc) -->

# Tabla de Contenidos

- [Tabla de Contenidos](#tabla-de-contenidos)
- [BioIntegrate](#biointegrate)
  - [🚀 Instalación y Configuración](#-instalación-y-configuración)
    - [1️⃣ Clonar el repositorio](#1️⃣-clonar-el-repositorio)
    - [2️⃣ Cambiar a la rama de desarrollo](#2️⃣-cambiar-a-la-rama-de-desarrollo)
    - [3️⃣ Crear entorno Conda](#3️⃣-crear-entorno-conda)
    - [4️⃣ Instalar el paquete en modo desarrollo](#4️⃣-instalar-el-paquete-en-modo-desarrollo)
    - [5️⃣ Configurar rutas personales](#5️⃣-configurar-rutas-personales)
  - [Quick Start](#quick-start)
  - [📥 Descargar Datos](#-descargar-datos)
  - [🗄️ Importar a JSON y MongoDB](#️-importar-a-json-y-mongodb)
  - [📊 Fuentes de Datos](#-fuentes-de-datos)
  - [🔧 Verificación](#-verificación)
  - [📖 Lectura](#-lectura)
  - [❓ Problemas Comunes](#-problemas-comunes)

<!-- TOC end -->

<!-- TOC --><a name="proyectoestandaresdatos"></a>
# BioIntegrate
Repositorio Github para el proyecto final de la asignatura "Estándares de Datos"

<!-- TOC --><a name="-instalación-y-configuración"></a>
## 🚀 Instalación y Configuración

<!-- TOC --><a name="1-clonar-el-repositorio"></a>
### 1️⃣ Clonar el repositorio

```bash
git clone https://github.com/MarioPasc/ProyectoEstandaresDatos.git
cd ProyectoEstandaresDatos
```

<!-- TOC --><a name="2-cambiar-a-la-rama-de-desarrollo"></a>
### 2️⃣ Cambiar a la rama de desarrollo

> [!IMPORTANT]
> **DEBES** trabajar en la rama `dev` para tener acceso a las últimas funcionalidades de descarga de datos.

```bash
git checkout dev
```

<!-- TOC --><a name="3-crear-entorno-conda"></a>
### 3️⃣ Crear entorno Conda

> [!WARNING]
> Se requiere **Python 3.9** específicamente. No uses otras versiones.

```bash
conda create -n estandares python=3.9 -y
conda activate estandares
```

<!-- TOC --><a name="4-instalar-el-paquete-en-modo-desarrollo"></a>
### 4️⃣ Instalar el paquete en modo desarrollo

```bash
pip install -e .
```

<!-- TOC --><a name="5-configurar-rutas-personales"></a>
### 5️⃣ Configurar rutas personales

> [!CAUTION]
> **CRÍTICO**: Debes personalizar las rutas de salida antes de ejecutar descargas.

```bash
# Editar el archivo y cambiar TODAS las rutas que contienen /home/mpascual
# por tu ruta personal (ver config/README.md para detalles)
nano config/data/{tu nombre}_data_config.yaml  # o usa tu editor preferido
```

**Rutas que debes cambiar** (6 en total):
- ✏️ `gdc.manifest_output`
- ✏️ `gdc.file_metadata_output`
- ✏️ `gdc.genes_output`
- ✏️ `gdc.rnaseq.output_dir`
- ✏️ `gdc.rnaseq.gene_table_output`
- ✏️ `hgnc.output_path`
- ✏️ `uniprot.mapping_output`
- ✏️ `uniprot.metadata_output`

📖 **Consulta** `config/README.md` para instrucciones detalladas.

## Quick Start

Se puede ejecutar el pipeline completo con:

```bash
  # Pipeline completo
  biointegrate-pipeline \
    --data-config config/data/mario_data_config.yaml \
    --mongo-config config/db_mongo/mario_mongodb_config.yaml

  # Solo crear JSONs sin insertar en MongoDB
  biointegrate-pipeline \
    --data-config config/data/mario_data_config.yaml \
    --mongo-config config/db_mongo/mario_mongodb_config.yaml \
    --no-insert

  # Omitir descarga (datos ya existen)
  biointegrate-pipeline \
    --data-config config/data/mario_data_config.yaml \
    --mongo-config config/db_mongo/mario_mongodb_config.yaml \
    --skip-download

  # Sin confirmación (ejecución directa)
  biointegrate-pipeline \
    --data-config config/data/mario_data_config.yaml \
    --mongo-config config/db_mongo/mario_mongodb_config.yaml \
    --yes
```

En el ordenador de Mario Pascual González:

```bash
====================================================================================================
PIPELINE COMPLETADO
====================================================================================================
  Estado:           EXITOSO
  Tiempo total:     2m 7s
  Descarga:         Ejecutada
  JSONs creados:    Sí
  MongoDB:          No (--no-insert)
  Evaluación:       Ejecutada

  Ficheros JSON generados:
    - GDC: /home/mpascual/misc/Universidad25-26/Estandares/data/gdc/gdc_collection_export.json
    - HGNC: /home/mpascual/misc/Universidad25-26/Estandares/data/hgnc/hgnc_collection_export.json
    - UniProt: /home/mpascual/misc/Universidad25-26/Estandares/data/uniprot/uniprot_collection_export.json
====================================================================================================
2025-11-22 09:51:27 - biointegrate.cli.pipeline - INFO - Pipeline completado exitosamente
```
<!-- TOC --><a name="-descargar-datos"></a>
## 📥 Descargar Datos

Una vez configurado tu archivo `config/data_config.yaml`:

```bash
# Descargar TODOS los datos (GDC + HGNC + UniProt)
biointegrate-download --config config/data_config.yaml --source all

# O descargar fuentes individuales:
biointegrate-download --config config/data_config.yaml --source gdc
biointegrate-download --config config/data_config.yaml --source hgnc
biointegrate-download --config config/data_config.yaml --source uniprot
```

> [!NOTE]
> - La descarga completa puede tardar varios minutos
> - UniProt requiere que GDC y HGNC se hayan descargado primero
> - Los directorios de salida se crean automáticamente

<!-- TOC --><a name="-importar-a-json-y-mongodb"></a>
## 🗄️ Importar a JSON y MongoDB

Una vez descargados los datos crudos, puedes procesarlos y convertirlos a formato JSON, y opcionalmente importarlos a MongoDB.

> [!CAUTION]
> **CRÍTICO**: Debes crear tu propio archivo de configuración de MongoDB.

```bash
# Crear tu archivo de configuración personalizado
cp config/db_mongo/mario_mongodb_config.yaml config/db_mongo/{tu_nombre}_mongodb_config.yaml

# Editar y cambiar TODAS las rutas que contienen /home/mpascual
nano config/db_mongo/{tu_nombre}_mongodb_config.yaml
```

**Comandos de importación:**

```bash
# Importar TODAS las fuentes (GDC + HGNC + UniProt) a JSON y MongoDB
biointegrate-import-all --config config/db_mongo/{tu_nombre}_mongodb_config.yaml

# Solo generar archivos JSON sin insertar en MongoDB
biointegrate-import-all --config config/db_mongo/{tu_nombre}_mongodb_config.yaml --no-insert

# Omitir fuentes específicas durante la importación
biointegrate-import-all --config config/db_mongo/{tu_nombre}_mongodb_config.yaml --skip-gdc
biointegrate-import-all --config config/db_mongo/{tu_nombre}_mongodb_config.yaml --skip-hgnc
biointegrate-import-all --config config/db_mongo/{tu_nombre}_mongodb_config.yaml --skip-uniprot
```

**Resultado esperado:**

Tras la ejecución exitosa, se generarán archivos JSON:
- ✅ **GDC**: ~7.6KB
- ✅ **HGNC**: ~139MB
- ✅ **UniProt**: ~5.8MB

> [!NOTE]
> - Los archivos JSON se generan incluso con `--no-insert`
> - La importación a MongoDB requiere tener MongoDB en ejecución
> - Los tres importadores (GDC, HGNC, UniProt) se ejecutan en secuencia

<!-- TOC --><a name="-ejecución-de-consultas-y-reportes-t2"></a>
## 🔍 Ejecución de Consultas y Reportes (T2)

El proyecto incluye un CLI dedicado para ejecutar consultas complejas sobre MongoDB y generar reportes transformados (JSON → XML → HTML).

### Comando Principal

```bash
biointegrate-execute-queries \
  --config config/queries/mario_queries.yaml \
  --queries docs/t2-queries/Query2Completa.txt,docs/t2-queries/Query1_LGG_UniProt.txt,docs/t2-queries/Query3_MembraneCancerCoverage.txt \
  --output-dir docs/t2-resultados \
  --xslt docs/xslt/biointegrate_report.xslt
```

### Flujo de Trabajo

1.  **Carga de Configuración**: Lee credenciales de MongoDB desde el YAML.
2.  **Ejecución**: Procesa los ficheros de consulta (`.txt`) contra la base de datos.
3.  **Transformación (T2)**:
    *   Guarda resultados crudos en `json/`.
    *   Convierte a XML en `xml/`.
    *   Aplica XSLT para generar reportes visuales en `html/`.

### Consultas Incluidas

*   **Query 1 (LGG UniProt)**: Proteómica dirigida para Glioma de Bajo Grado.
*   **Query 2 (Completa)**: Integración multi-ómica (Clínica + Genómica + Proteómica).
*   **Query 3 (Cobertura)**: Análisis de disponibilidad de datos para proteínas de membrana en cáncer.

Para más detalles técnicos, consulta la [Guía de Lectura del CLI](docs/reports/guia_lectura_queries_cli.html).

<!-- TOC --><a name="-fuentes-de-datos"></a>
## 📊 Fuentes de Datos

- **GDC (Genomic Data Commons)**: Datos RNA-seq del proyecto TCGA-LGG
- **HGNC**: Nomenclatura completa de genes humanos
- **UniProt**: Anotación de proteínas asociadas a los genes del proyecto

<!-- TOC --><a name="-verificación"></a>
## 🔧 Verificación

Después de la descarga, el sistema muestra automáticamente:
- ✅ Estadísticas de archivos descargados
- ✅ Número de registros y columnas
- ✅ Validaciones de integridad

<!-- TOC --><a name="-lectura"></a>
## 📖 Lectura

Por favor! Leed con detenimiento [este fichero](docs/reports/T1_README_Datos.md), describe todo lo que creo que deberíamos de saber de los datos antes de empezar a trabajar con ellos 

<!-- TOC --><a name="-problemas-comunes"></a>
## ❓ Problemas Comunes

**Error: "No such file or directory"**
→ Verifica que las rutas en `data_config.yaml` existan y tengas permisos de escritura

**Error: "Archivo requerido no encontrado"** (al descargar UniProt)
→ Descarga primero GDC y HGNC: `--source gdc` y `--source hgnc`

**Error: "Python version mismatch"**
→ Asegúrate de usar Python 3.9: `python --version`
